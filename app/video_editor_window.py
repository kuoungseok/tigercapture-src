from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QThread, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.audio_tracks import (
    AUDIO_EXTS,
    VIDEO_EXTS,
    AudioClip,
    AudioMixer,
    AudioTrack,
    WaveformExtractor,
    is_audio_path,
    is_video_path,
    probe_audio_duration_ms,
)
from app.drawing import (
    DrawingCanvas,
    SpeechBubble,
    SpeechBubbleItem,
    Stroke,
    compose_pil_bubbles,
)
from app.i18n import tr
from app.project_player import ProjectPlayer
from app.simple_video_player import PlayerState
from app.subtitles import Subtitle, SubtitlePanel
from app.video_exporter import VideoExportThread, build_segments


SPEED_CHOICES = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0]
THUMB_H = 48                  # thumbnail extract/display height in pixels
THUMB_SECONDS_PER_TILE = 4.0  # target seconds between thumbnails
MIN_THUMBS = 10
MAX_THUMBS = 60
TRACK_HEIGHT = 70
TRACK_V_PADDING = 8
DEFAULT_PX_PER_SEC = 40.0
MIN_PX_PER_SEC = 4.0
MAX_PX_PER_SEC = 300.0
MIN_TRACK_WIDTH = 300

FADE_MIME_TYPE = "application/x-gifcam-transition"


from app.style import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_BLUE_HOVER,
    COLOR_ACCENT_GREEN,
    COLOR_ACCENT_ORANGE,
    COLOR_BG_L1,
    COLOR_BG_L2,
    COLOR_BG_L3,
    COLOR_BG_L4,
    COLOR_BG_L5,
    COLOR_BORDER_DEFAULT,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
)


VIDEO_EDITOR_EXTRA_QSS = f"""
QWidget#EditorRoot {{
    background-color: {COLOR_BG_L3};
    color: {COLOR_TEXT_SECONDARY};
}}

QLabel {{
    color: {COLOR_TEXT_SECONDARY};
    background: transparent;
}}

QPushButton#ToolButton {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 7px 13px;
    font-weight: 500;
}}
QPushButton#ToolButton:hover {{
    background-color: {COLOR_BG_L5};
    border-color: #5a5a62;
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton#ToolButton:pressed {{
    background-color: #0a0a0e;
}}
QPushButton#ToolButton:disabled {{
    color: {COLOR_TEXT_DISABLED};
    border-color: {COLOR_BORDER_SUBTLE};
}}
QPushButton#ToolButton:checked {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_ACCENT_BLUE};
}}

QPushButton#PrimaryToolButton {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 700;
}}
QPushButton#PrimaryToolButton:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
}}
QPushButton#PrimaryToolButton:pressed {{
    background-color: #2a6fb4;
}}

QPushButton#SpeedActive {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_ACCENT_BLUE};
    border-radius: 6px;
    padding: 5px 11px;
    font-weight: 700;
}}

QLabel[sectionHeader="true"] {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    padding: 8px 12px 8px 16px;
    background-color: {COLOR_BG_L4};
    border-left: 4px solid {COLOR_ACCENT_BLUE};
}}
QLabel[sectionHeader="true"][accent="preview"] {{
    border-left: 4px solid {COLOR_ACCENT_BLUE};
}}
QLabel[sectionHeader="true"][accent="timeline"] {{
    border-left: 4px solid {COLOR_ACCENT_ORANGE};
}}
QLabel[sectionHeader="true"][accent="subtitles"] {{
    border-left: 4px solid {COLOR_ACCENT_GREEN};
}}

/* Preview section header: custom row that replaces the plain QLabel
   version so we can embed the pop-out icon button on the right. The
   container carries the accent bar + bg; the inner title QLabel
   matches the generic sectionHeader look but without its own bg so
   everything reads as one strip. */
QWidget#PreviewSectionHeader {{
    background-color: {COLOR_BG_L4};
    border-left: 4px solid {COLOR_ACCENT_BLUE};
}}
QLabel#PreviewSectionTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    padding: 8px 12px 8px 12px;
    background: transparent;
}}
QPushButton#PreviewPopoutIcon {{
    background-color: transparent;
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: 4px;
    font-size: 15px;
    padding: 0;
}}
QPushButton#PreviewPopoutIcon:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_BORDER_DEFAULT};
}}
QPushButton#PreviewPopoutIcon:pressed {{
    background-color: {COLOR_BG_L2};
}}
QPushButton#PreviewPopoutIcon[popped="true"] {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_ACCENT_BLUE};
}}

QWidget#PreviewHost {{
    background-color: {COLOR_BG_L1};
    border: none;
}}

QWidget#PlayBar {{
    background-color: {COLOR_BG_L4};
    border-top: 3px solid {COLOR_BG_L1};
    border-bottom: 3px solid {COLOR_BG_L1};
}}

QWidget#ControlsBar {{
    background-color: {COLOR_BG_L3};
    border-top: 3px solid {COLOR_BG_L1};
}}

QLabel#TimeLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 13px;
    font-weight: 600;
}}
QLabel#SpeedLabel {{
    color: {COLOR_ACCENT_BLUE};
    font-family: 'Consolas', 'Monaco', monospace;
    font-weight: 700;
}}
QLabel#ZoomLabel {{
    color: {COLOR_TEXT_TERTIARY};
    font-family: 'Consolas', 'Monaco', monospace;
}}

QPushButton#PlayButton {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    border-radius: 19px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#PlayButton:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
}}

QScrollArea {{
    background: {COLOR_BG_L2};
    border: none;
}}
QScrollBar:horizontal {{
    background: {COLOR_BG_L2};
    height: 10px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER_DEFAULT};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #5a5a62;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {COLOR_BG_L2};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER_DEFAULT};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #5a5a62;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
}}

QListWidget {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 4px;
    alternate-background-color: {COLOR_BG_L3};
}}
QListWidget::item {{
    padding: 4px 8px;
}}
QListWidget::item:selected {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
}}
"""


@dataclass
class SpeedSegment:
    start_ms: int
    end_ms: int
    speed: float

    def contains(self, ms: int) -> bool:
        return self.start_ms <= ms < self.end_ms

    def overlaps(self, other_start: int, other_end: int) -> bool:
        return not (self.end_ms <= other_start or other_end <= self.start_ms)


@dataclass
class CutSegment:
    start_ms: int
    end_ms: int
    fade_ms: int = 0  # legacy, no longer used by exporter (kept for save compat)

    def contains(self, ms: int) -> bool:
        return self.start_ms <= ms < self.end_ms


@dataclass
class FadeSegment:
    """A draggable fade transition placed on the track.
    ``kind``:
      - ``both``: fade-out during first half, fade-in during second half
      - ``in``:   fade-in (black → content) across the whole span
      - ``out``:  fade-out (content → black) across the whole span
    Width of the actor = full duration of the effect."""

    start_ms: int
    end_ms: int
    kind: str = "both"

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def contains(self, ms: int) -> bool:
        return self.start_ms <= ms < self.end_ms


@dataclass
class VideoTrack:
    id: int
    source_path: Path | None = None
    duration_ms: int = 0
    offset_ms: int = 0  # where this clip starts on the project timeline
    speed_segments: list[SpeedSegment] = field(default_factory=list)
    cuts: list[CutSegment] = field(default_factory=list)
    fades: list[FadeSegment] = field(default_factory=list)
    thumbnails: list[QPixmap] = field(default_factory=list)
    selection_start_ms: int = -1
    selection_end_ms: int = -1

    @property
    def display_name(self) -> str:
        if self.source_path is None:
            return tr("veditor.track.empty")
        return self.source_path.name


class ThumbnailExtractor(QThread):
    """Extracts evenly-spaced thumbnail frames for a track's video using
    OpenCV. The count is chosen dynamically from video duration so that one
    thumbnail roughly represents ``THUMB_SECONDS_PER_TILE`` of footage,
    clamped to [MIN_THUMBS, MAX_THUMBS]."""

    count_determined = Signal(int, int)  # track_id, count
    thumb_ready = Signal(int, int, QPixmap)  # track_id, index, pixmap
    finished_extracting = Signal(int)  # track_id

    def __init__(
        self,
        track_id: int,
        path: Path,
        thumb_height: int,
    ) -> None:
        super().__init__()
        self._track_id = track_id
        self._path = Path(path)
        self._thumb_h = max(16, int(thumb_height))
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        cap = None
        try:
            import cv2
            import numpy as np

            cap = cv2.VideoCapture(str(self._path))
            if not cap.isOpened():
                return
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if total_frames <= 0:
                return
            duration_s = total_frames / fps if fps > 0 else 0
            count = max(
                MIN_THUMBS,
                min(MAX_THUMBS, int(round(duration_s / THUMB_SECONDS_PER_TILE))),
            )
            self.count_determined.emit(self._track_id, count)

            for i in range(count):
                if self._stop:
                    return
                frame_idx = min(
                    total_frames - 1,
                    int((i + 0.5) * total_frames / count),
                )
                # Seek to the nearest keyframe and read — O(1) after cap is open
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, bgr = cap.read()
                if not ret or bgr is None:
                    continue

                h, w = bgr.shape[:2]
                if h != self._thumb_h:
                    new_w = max(1, int(round(w * self._thumb_h / h)))
                    bgr = cv2.resize(
                        bgr, (new_w, self._thumb_h), interpolation=cv2.INTER_AREA
                    )
                    h, w = bgr.shape[:2]
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                contig = np.ascontiguousarray(rgb)
                qimg = QImage(
                    contig.data, w, h, contig.strides[0], QImage.Format.Format_RGB888
                ).copy()
                pixmap = QPixmap.fromImage(qimg)
                self.thumb_ready.emit(self._track_id, i, pixmap)
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            self.finished_extracting.emit(self._track_id)


class TimelineRuler(QWidget):
    """Horizontal time ruler shared by all tracks. Uses the same MARGIN as
    ``TrackRow`` so tick marks line up exactly with track contents. Scrolls
    horizontally with the track list (sits at the top of the same scroll
    viewport).

    Also acts as the scrub zone — click/drag on the ruler to seek the
    project playhead. Emits ``scrub_requested(project_ms)``.
    """

    scrub_requested = Signal(int)  # project_ms

    HEIGHT = 30
    MARGIN = 10  # matches TrackRow.MARGIN
    BASELINE_DURATION_MS = 30_000  # ruler width when no tracks are loaded

    def __init__(self) -> None:
        super().__init__()
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        self._duration_ms: int = 0
        self._playhead_ms: int = 0
        self._scrubbing: bool = False
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setToolTip(tr("veditor.ruler.hint"))
        self._recalc_width()

    def _x_to_project_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._scrubbing = True
        self.scrub_requested.emit(self._x_to_project_ms(event.position().toPoint().x()))

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
        painter.fillRect(self.rect(), QColor(COLOR_BG_L4))

        # Top separator line (matches the spec's .time-ruler border-top)
        painter.setPen(QColor("#2a2a30"))
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
        target_px = 72  # aim for ~72 px between major labels
        raw = target_px / self._px_per_sec
        nice_steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
        interval_s = next((n for n in nice_steps if raw <= n), 600)
        minor_s = interval_s / 5.0

        # Layout: tick marks on top, labels directly below.
        tick_top = 3
        tick_bot = tick_top + 4          # minor ticks = 4 px tall
        major_tick_bot = tick_top + 7    # major ticks = 7 px tall
        label_baseline = self.HEIGHT - 6

        # Minor ticks
        painter.setPen(QColor(COLOR_BORDER_DEFAULT))
        t = 0.0
        while t <= total_s + 1e-6:
            x = int(self.MARGIN + t * self._px_per_sec)
            painter.drawLine(x, tick_top, x, tick_bot)
            t += minor_s

        # Major ticks
        painter.setPen(QColor(COLOR_TEXT_TERTIARY))
        t = 0.0
        while t <= total_s + 1e-6:
            x = int(self.MARGIN + t * self._px_per_sec)
            painter.drawLine(x, tick_top, x, major_tick_bot)
            t += interval_s

        # Time labels (centered under each major tick)
        painter.setPen(QColor(COLOR_TEXT_TERTIARY))
        font = painter.font()
        font.setPixelSize(10)
        font.setFamily("Monaco, Consolas, monospace")
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

        # Playhead — orange with glow + diamond handle
        px = int(self.MARGIN + self._playhead_ms / 1000.0 * self._px_per_sec)
        glow = QPen(QColor(216, 90, 48, 90))
        glow.setWidth(6)
        painter.setPen(glow)
        painter.drawLine(px, 0, px, self.HEIGHT)
        pen = QPen(QColor(COLOR_ACCENT_ORANGE))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(px, 0, px, self.HEIGHT)
        painter.setBrush(QColor(COLOR_ACCENT_ORANGE))
        painter.setPen(QColor("#ff7a4a"))
        diamond = [
            QPoint(px, 2),
            QPoint(px + 5, 7),
            QPoint(px, 12),
            QPoint(px - 5, 7),
        ]
        from PySide6.QtGui import QPolygon
        painter.drawPolygon(QPolygon(diamond))


class TrackRow(QWidget):
    """Single horizontal track with label row + timeline row."""

    clicked = Signal(int)  # track_id
    position_requested = Signal(int, int)  # track_id, ms
    selection_changed = Signal(int, int, int)  # track_id, start, end
    context_menu = Signal(int, QPoint)  # track_id, global_pos

    MARGIN = 10
    LABEL_H = 18
    TIMELINE_H = TRACK_HEIGHT
    FADE_EDGE_GRAB_PX = 6  # resize handle hit area in pixels

    offset_changed = Signal(int, int)  # track_id, new_offset_ms
    fades_changed = Signal(int)  # track_id — fade segments added / resized
    media_dropped = Signal(int, object)  # track_id, Path — any media file

    def __init__(self, track: VideoTrack) -> None:
        super().__init__()
        self.track = track
        self._is_active: bool = False
        self._position_ms: int = 0  # project time
        self._dragging_selection: bool = False
        self._dragging_playhead: bool = False
        self._dragging_offset: bool = False
        self._resizing_fade: FadeSegment | None = None
        self._resize_side: str = ""  # "left" or "right"
        self._resize_orig_start: int = 0
        self._resize_orig_end: int = 0
        self._drag_start_ms: int = 0
        self._drag_start_x: int = 0
        self._drag_start_offset_ms: int = 0
        self._px_per_sec: float = DEFAULT_PX_PER_SEC

        self.setFixedHeight(self.LABEL_H + self.TIMELINE_H + TRACK_V_PADDING)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        # Transparent background so the parent's stripe pattern shows through
        # in the label row and around any empty clip.
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.setAcceptDrops(True)
        self._recalc_width()

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self._recalc_width()

    def _preferred_width(self) -> int:
        """Content-driven width (offset + duration) before any stretching."""
        if self.track.duration_ms <= 0:
            return MIN_TRACK_WIDTH
        span_ms = self.track.offset_ms + self.track.duration_ms
        w = int(span_ms / 1000.0 * self._px_per_sec) + 2 * self.MARGIN
        return max(MIN_TRACK_WIDTH, w)

    def _recalc_width(self) -> None:
        # Set the content-driven minimum; the editor will stretch every row
        # to the widest common width via _update_tracks_host_width.
        self.setFixedWidth(self._preferred_width())
        self.update()

    def set_active(self, active: bool) -> None:
        if self._is_active != active:
            self._is_active = active
            self.update()

    def set_position(self, ms: int) -> None:
        self._position_ms = ms
        self.update()

    def _timeline_rect(self) -> QRect:
        """Rect of the clip body in widget coords (starts at offset)."""
        offset_px = int(self.track.offset_ms / 1000.0 * self._px_per_sec)
        duration_px = int(self.track.duration_ms / 1000.0 * self._px_per_sec)
        return QRect(
            self.MARGIN + offset_px,
            self.LABEL_H,
            max(0, duration_px),
            self.TIMELINE_H,
        )

    def _project_ms_to_x(self, project_ms: int) -> int:
        """Project-timeline ms → widget x."""
        return int(self.MARGIN + project_ms / 1000.0 * self._px_per_sec)

    def _x_to_project_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def _ms_to_x(self, ms: int) -> int:
        """Track-local ms → widget x (accounts for offset)."""
        return self._project_ms_to_x(self.track.offset_ms + ms)

    def _x_to_ms(self, x: int) -> int:
        """Widget x → track-local ms (clamped to duration)."""
        if self.track.duration_ms <= 0:
            return 0
        local = self._x_to_project_ms(x) - self.track.offset_ms
        return max(0, min(self.track.duration_ms, local))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Active indicator dot + track label
        if self._is_active:
            label_color = QColor(COLOR_ACCENT_BLUE)
            status_color = QColor(COLOR_ACCENT_GREEN)
        else:
            label_color = QColor(COLOR_TEXT_TERTIARY)
            status_color = QColor(COLOR_TEXT_DISABLED)
        painter.setPen(status_color)
        painter.drawText(
            QRect(self.MARGIN, 0, 14, self.LABEL_H),
            Qt.AlignmentFlag.AlignVCenter,
            "●" if self._is_active else "○",
        )
        painter.setPen(label_color)
        painter.drawText(
            QRect(self.MARGIN + 16, 0, self.width() - 2 * self.MARGIN - 16, self.LABEL_H),
            Qt.AlignmentFlag.AlignVCenter,
            self.track.display_name,
        )

        rect = self._timeline_rect()

        if self.track.source_path is None:
            # Empty slot: BRIGHTER diagonal stripes than the host background,
            # with a dashed border — matches the 3-level hierarchy
            # (timeline host = darkest, loaded clip = middle, empty = lightest).
            self._paint_empty_slot_pattern(painter, rect)
            painter.setPen(QColor("#8a8a92"))
            font = painter.font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter,
                tr("veditor.track.no_source"),
            )
        else:
            # Loaded clip — ~30% darker than the host bg so the filled content
            # reads as "sunken" against the brighter background.
            painter.fillRect(rect, QColor("#141418"))
            pen = QPen(QColor("#262630"))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

            # Thumbnails — fixed native aspect, centered on their time position.
            if self.track.thumbnails and self.track.duration_ms > 0:
                n = len(self.track.thumbnails)
                track_h = rect.height()
                for i, pm in enumerate(self.track.thumbnails):
                    if pm is None or pm.isNull():
                        continue
                    if pm.height() > 0:
                        tw = max(1, int(round(pm.width() * track_h / pm.height())))
                    else:
                        tw = 80
                    time_ms = (i + 0.5) * self.track.duration_ms / n
                    center_x = self._ms_to_x(int(time_ms))
                    x = center_x - tw // 2
                    painter.drawPixmap(x, rect.top(), tw, track_h, pm)
            else:
                painter.setPen(QColor(COLOR_TEXT_TERTIARY))
                painter.drawText(
                    rect, Qt.AlignmentFlag.AlignCenter,
                    tr("veditor.track.loading"),
                )

        # Speed segments overlay
        for seg in self.track.speed_segments:
            x1 = self._ms_to_x(seg.start_ms)
            x2 = self._ms_to_x(seg.end_ms)
            seg_w = max(1, x2 - x1)
            color = self._color_for_speed(seg.speed)
            painter.fillRect(x1, rect.top(), seg_w, rect.height(), color)
            self._draw_speed_label(
                painter, seg.speed, x1, rect.top(), seg_w, rect.height()
            )

        # Cut segments (dark overlay)
        for cut in self.track.cuts:
            x1 = self._ms_to_x(cut.start_ms)
            x2 = self._ms_to_x(cut.end_ms)
            painter.fillRect(
                x1, rect.top(), max(1, x2 - x1), rect.height(),
                QColor(30, 30, 30, 200),
            )
            if x2 - x1 > 24:
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(
                    QRect(x1, rect.top(), x2 - x1, rect.height()),
                    Qt.AlignmentFlag.AlignCenter,
                    tr("veditor.cut_label"),
                )

        # Fade segments — orange gradient "actors", resizable via edge drag.
        for fade in self.track.fades:
            self._paint_fade_segment(painter, fade, rect)

        # Selection
        sel_start = self.track.selection_start_ms
        sel_end = self.track.selection_end_ms
        if sel_start >= 0 and sel_end > sel_start:
            sx1 = self._ms_to_x(sel_start)
            sx2 = self._ms_to_x(sel_end)
            painter.fillRect(
                sx1, rect.top(), max(1, sx2 - sx1), rect.height(),
                QColor(55, 138, 221, 80),
            )
            pen = QPen(QColor(COLOR_ACCENT_BLUE))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(sx1, rect.top(), max(1, sx2 - sx1), rect.height())

        # Active track border
        if self._is_active:
            pen = QPen(QColor(COLOR_ACCENT_BLUE))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

        # Playhead — orange, drawn on every track at project time.
        pen = QPen(QColor(COLOR_ACCENT_ORANGE))
        pen.setWidth(2)
        painter.setPen(pen)
        px = self._project_ms_to_x(self._position_ms)
        painter.drawLine(
            px, self.LABEL_H - 2, px, self.LABEL_H + self.TIMELINE_H + 2
        )

        # Separator between track rows — dark groove against the bright host
        # stripes so adjacent tracks read as distinct lanes.
        pen = QPen(QColor("#0f0f14"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(
            0, self.height() - 1, self.width(), self.height() - 1,
        )

    @staticmethod
    def _color_for_speed(speed: float) -> QColor:
        if speed < 1.0:
            t = min(1.0, (1.0 - speed) / 0.75)
            return QColor(int(120 + 80 * t), int(180 - 80 * t), 255, 160)
        if speed > 1.0:
            t = min(1.0, (speed - 1.0) / 15.0)
            return QColor(255, int(180 - 130 * t), int(120 - 100 * t), 160)
        return QColor(150, 150, 150, 100)

    def _paint_fade_segment(
        self, painter: QPainter, fade: FadeSegment, rect: QRect
    ) -> None:
        """Draw a FadeSegment as an orange/black gradient. Shape depends on
        ``fade.kind``: ``in`` = black→content, ``out`` = content→black,
        ``both`` = content→black→content (two halves). Resize handles on
        each edge; right-click menu toggles the kind."""
        from PySide6.QtGui import QLinearGradient, QBrush
        fx1 = self._ms_to_x(fade.start_ms)
        fx2 = self._ms_to_x(fade.end_ms)
        if fx2 - fx1 < 2:
            return

        painter.save()
        painter.setClipRect(
            rect.intersected(QRect(fx1, rect.top(), fx2 - fx1, rect.height()))
        )
        if fade.kind == "in":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 220))
            g.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(fx1, rect.top(), fx2 - fx1, rect.height(), QBrush(g))
        elif fade.kind == "out":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(216, 90, 48, 0))
            g.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, rect.top(), fx2 - fx1, rect.height(), QBrush(g))
        else:  # both — two-half pattern
            mid = (fx1 + fx2) // 2
            g_out = QLinearGradient(fx1, 0, mid, 0)
            g_out.setColorAt(0.0, QColor(216, 90, 48, 0))
            g_out.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, rect.top(), mid - fx1, rect.height(), QBrush(g_out))
            g_in = QLinearGradient(mid, 0, fx2, 0)
            g_in.setColorAt(0.0, QColor(0, 0, 0, 220))
            g_in.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(mid, rect.top(), fx2 - mid, rect.height(), QBrush(g_in))
        painter.restore()

        # Outer frame — orange, solid so the actor reads as one unit.
        pen = QPen(QColor(COLOR_ACCENT_ORANGE))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(fx1, rect.top(), max(1, fx2 - fx1), rect.height())

        # Edge handles (small vertical bars) to invite resizing.
        handle_w = 3
        handle_color = QColor(255, 150, 80)
        painter.fillRect(fx1 - handle_w // 2, rect.top(), handle_w, rect.height(), handle_color)
        painter.fillRect(fx2 - handle_w // 2, rect.top(), handle_w, rect.height(), handle_color)

    @staticmethod
    def _paint_empty_slot_pattern(painter: QPainter, rect: QRect) -> None:
        """Empty-track rectangle with dashed border. Stripes are already
        visible through from the parent StripedHost (empty area = background),
        so we only need the border outline here."""
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        border = QPen(QColor("#4a4a52"))
        border.setStyle(Qt.PenStyle.DashLine)
        border.setWidth(1)
        painter.setPen(border)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.restore()

    @staticmethod
    def _draw_speed_label(
        painter: QPainter, speed: float, x: int, y: int, w: int, h: int
    ) -> None:
        """Draw a bold ×speed badge clamped inside the segment rect. Picks a
        font size proportional to the segment box, capped so it never spills
        outside the track frame."""
        if w < 14:
            return
        label = f"×{speed:g}"
        # Font size scales with the smaller of segment width / track height,
        # so very narrow segments get a small readable label instead of an
        # oversized clipped one.
        target_h = min(h - 4, int(w * 0.55))
        font_px = max(11, min(36, target_h))
        font = painter.font()
        font.setPixelSize(font_px)
        font.setBold(True)
        painter.setFont(font)

        # White text with a dark outline for legibility on any speed color.
        clip_rect = QRect(x, y, w, h)
        painter.save()
        painter.setClipRect(clip_rect)
        # Shadow / outline via 1px offsets
        painter.setPen(QColor(0, 0, 0, 220))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            painter.drawText(
                clip_rect.adjusted(dx, dy, dx, dy),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(clip_rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.clicked.emit(self.track.id)
        if self.track.duration_ms <= 0:
            return
        pos = event.position().toPoint()
        x = pos.x()
        mods = event.modifiers()
        rect = self._timeline_rect()

        # Fade edge resize takes priority over everything else.
        fade, side = self._fade_edge_at(x, pos.y())
        if fade is not None:
            self._resizing_fade = fade
            self._resize_side = side
            self._resize_orig_start = fade.start_ms
            self._resize_orig_end = fade.end_ms
            self._drag_start_x = x
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        # Shift+drag inside the clip body = range select.
        if mods & Qt.KeyboardModifier.ShiftModifier:
            if not rect.contains(pos):
                return
            ms = self._x_to_ms(x)
            self._dragging_selection = True
            self._drag_start_ms = ms
            self.track.selection_start_ms = ms
            self.track.selection_end_ms = ms
            self.update()
            return

        # Drag on the clip body = move the clip on the project timeline
        # (Premiere/DaVinci style). Scrubbing moved to the timeline ruler.
        if rect.contains(pos):
            self._dragging_offset = True
            self._drag_start_x = x
            self._drag_start_offset_ms = self.track.offset_ms
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.track.duration_ms <= 0:
            return
        pos = event.position().toPoint()
        x = pos.x()

        # Fade edge resize — active drag
        if self._resizing_fade is not None:
            delta_ms = int((x - self._drag_start_x) / self._px_per_sec * 1000)
            fade = self._resizing_fade
            if self._resize_side == "left":
                new_start = max(0, min(
                    fade.end_ms - 100,
                    self._resize_orig_start + delta_ms,
                ))
                fade.start_ms = new_start
            else:  # "right"
                new_end = min(self.track.duration_ms, max(
                    fade.start_ms + 100,
                    self._resize_orig_end + delta_ms,
                ))
                fade.end_ms = new_end
            self.update()
            self.fades_changed.emit(self.track.id)
            return

        # Idle hover — swap cursor when the pointer is over a fade edge so
        # the user discovers that edges are resizable.
        if not (self._dragging_offset or self._dragging_selection
                or self._dragging_playhead):
            fade, _side = self._fade_edge_at(x, pos.y())
            if fade is not None:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)

        if self._dragging_offset:
            delta_px = x - self._drag_start_x
            delta_ms = int(delta_px / self._px_per_sec * 1000)
            new_offset = max(0, self._drag_start_offset_ms + delta_ms)
            if new_offset != self.track.offset_ms:
                self.track.offset_ms = new_offset
                self._recalc_width()
                # Emit live so the project duration/ruler update during drag,
                # not only on release.
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
            return
        if self._dragging_selection:
            ms = self._x_to_ms(x)
            self.track.selection_start_ms = min(self._drag_start_ms, ms)
            self.track.selection_end_ms = max(self._drag_start_ms, ms)
            self.update()
        elif self._dragging_playhead:
            project_ms = self._x_to_project_ms(x)
            self.position_requested.emit(self.track.id, project_ms)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._resizing_fade is not None:
            self._resizing_fade = None
            self._resize_side = ""
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.fades_changed.emit(self.track.id)
        if self._dragging_offset:
            self._dragging_offset = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
        if self._dragging_selection:
            self._dragging_selection = False
            if self.track.selection_end_ms - self.track.selection_start_ms < 50:
                self.track.selection_start_ms = -1
                self.track.selection_end_ms = -1
            self.selection_changed.emit(
                self.track.id,
                self.track.selection_start_ms,
                self.track.selection_end_ms,
            )
            self.update()
        self._dragging_playhead = False

    def _on_context_menu(self, local_pos: QPoint) -> None:
        # If the click is on a fade actor, open the fade-type / delete menu
        # instead of the generic track menu.
        fade = self._fade_under(local_pos)
        if fade is not None:
            self._show_fade_menu(fade, self.mapToGlobal(local_pos))
            return
        self.context_menu.emit(self.track.id, self.mapToGlobal(local_pos))

    def _fade_under(self, pos: QPoint) -> FadeSegment | None:
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        ms = self._x_to_ms(pos.x())
        for fade in self.track.fades:
            if fade.contains(ms):
                return fade
        return None

    def _show_fade_menu(self, fade: FadeSegment, global_pos) -> None:
        menu = QMenu(self)
        act_in = menu.addAction(tr("veditor.fade_menu.in"))
        act_in.setCheckable(True)
        act_in.setChecked(fade.kind == "in")
        act_out = menu.addAction(tr("veditor.fade_menu.out"))
        act_out.setCheckable(True)
        act_out.setChecked(fade.kind == "out")
        act_both = menu.addAction(tr("veditor.fade_menu.both"))
        act_both.setCheckable(True)
        act_both.setChecked(fade.kind == "both")
        menu.addSeparator()
        act_del = menu.addAction(tr("veditor.fade_menu.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_in:
            fade.kind = "in"
        elif chosen is act_out:
            fade.kind = "out"
        elif chosen is act_both:
            fade.kind = "both"
        elif chosen is act_del:
            try:
                self.track.fades.remove(fade)
            except ValueError:
                pass
        else:
            return
        self.update()
        self.fades_changed.emit(self.track.id)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # Double-click on a fade segment deletes it.
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        pos = event.position().toPoint()
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return
        ms = self._x_to_ms(pos.x())
        for fade in list(self.track.fades):
            if fade.contains(ms):
                self.track.fades.remove(fade)
                self.update()
                self.fades_changed.emit(self.track.id)
                return

    # ---------- fade segment hit-testing / drag-drop ----------

    def _fade_edge_at(self, x: int, y: int) -> tuple[FadeSegment | None, str]:
        """Return (fade, 'left' / 'right') if the cursor sits on either edge
        of a placed FadeSegment inside the timeline area."""
        if y < self.LABEL_H or y > self.LABEL_H + self.TIMELINE_H:
            return None, ""
        for fade in self.track.fades:
            fx1 = self._ms_to_x(fade.start_ms)
            fx2 = self._ms_to_x(fade.end_ms)
            if abs(x - fx1) <= self.FADE_EDGE_GRAB_PX:
                return fade, "left"
            if abs(x - fx2) <= self.FADE_EDGE_GRAB_PX:
                return fade, "right"
        return None, ""

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat(FADE_MIME_TYPE):
            event.acceptProposedAction()
            return
        # Accept any media file (video OR audio); the window will route
        # mismatches to the right track type. Qt does not automatically
        # propagate drags from a dropAccepting child to its parent —
        # so we swallow the event here and emit our own signal.
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_video_path(p) or is_audio_path(p):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat(FADE_MIME_TYPE):
            try:
                duration_ms = int(bytes(md.data(FADE_MIME_TYPE)).decode("utf-8"))
            except Exception:
                duration_ms = FadeCard.DEFAULT_DURATION_MS
            duration_ms = max(100, duration_ms)
            if self.track.duration_ms <= 0:
                return
            center_ms = self._x_to_ms(event.position().toPoint().x())
            start = max(0, center_ms - duration_ms // 2)
            end = min(self.track.duration_ms, start + duration_ms)
            if end <= start:
                return
            self.track.fades.append(FadeSegment(start, end))
            self.track.fades.sort(key=lambda f: f.start_ms)
            self.update()
            self.fades_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return
        # Any media file dropped onto this row — let the window route.
        # Video → fill empty track or add new. Audio → add new audio track.
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_video_path(p) or is_audio_path(p):
                    self.media_dropped.emit(self.track.id, p)
                    event.acceptProposedAction()
                    return
        event.ignore()


class FadeCard(QWidget):
    """Draggable "Fade" transition card. Drag-drop onto a track creates a
    FadeSegment at the drop position; the embedded combo's value sets the
    new segment's default duration."""

    DEFAULT_DURATION_MS = 400

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("FadeCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(120)
        self.setStyleSheet(
            f"""
            QWidget#FadeCard {{
                background-color: {COLOR_BG_L5};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QWidget#FadeCard:hover {{
                border-color: {COLOR_ACCENT_ORANGE};
            }}
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 12, 4)
        row.setSpacing(8)

        swatch = _FadeSwatch()
        swatch.setFixedSize(44, 22)
        row.addWidget(swatch)

        title = QLabel(tr("veditor.fade_card.title"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 700;")
        row.addWidget(title)

        self.setToolTip(tr("veditor.fade_card.hint"))

    def selected_duration_ms(self) -> int:
        return self.DEFAULT_DURATION_MS

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDrag

        mime = QMimeData()
        mime.setData(FADE_MIME_TYPE, str(self.selected_duration_ms()).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _FadeSwatch(QWidget):
    """Mini horizontal fade gradient — doubles as a visual "icon" for the
    Fade transition card. Black → orange glow → transparent."""

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        # Left half: fade-out (content → black)
        g1 = QLinearGradient(0, 0, w / 2, 0)
        g1.setColorAt(0.0, QColor("#4a6a8a"))
        g1.setColorAt(1.0, QColor("#0a0a0e"))
        painter.fillRect(0, 0, int(w / 2), h, QBrush(g1))
        # Right half: fade-in (black → content) with an orange glow join
        g2 = QLinearGradient(w / 2, 0, w, 0)
        g2.setColorAt(0.0, QColor("#0a0a0e"))
        g2.setColorAt(0.5, QColor(216, 90, 48, 180))
        g2.setColorAt(1.0, QColor("#4a6a8a"))
        painter.fillRect(int(w / 2), 0, w - int(w / 2), h, QBrush(g2))
        # Vertical join marker
        pen = QPen(QColor(COLOR_ACCENT_ORANGE))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(int(w / 2), 0, int(w / 2), h)


class StripedHost(QWidget):
    """Scrollable timeline host. Paints a continuous 45° diagonal-stripe
    pattern as its background so gaps between tracks and empty areas inside
    tracks all show the same "timeline canvas" look."""

    BG = QColor("#373744")
    STRIPE = QColor("#454554")
    STRIPE_WIDTH = 10
    STRIPE_STEP = 20

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.BG)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self.STRIPE)
        pen.setWidth(self.STRIPE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        h = self.height()
        x_start = -h
        x_end = self.width() + h
        x = x_start - (x_start % self.STRIPE_STEP)
        while x <= x_end:
            painter.drawLine(x, 0, x + h, h)
            x += self.STRIPE_STEP


class ClipWaveformView(QWidget):
    """Interactive waveform renderer for a single AudioClip.

    Renders the effective trim range stretched across the widget width,
    with cuts as dark overlays, fade segments as orange gradients,
    markers as cyan dots, selection as a translucent blue band, and a
    vertical playhead when driven by the sound editor's player.

    Inputs:
    - click (anywhere)   → scrub the playhead (``scrub_requested``)
    - shift + drag       → build a selection range (``selection_changed``)
    - double-click       → clear the current selection
    - right-click on a marker → ``marker_right_clicked``
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
            f"background-color: {COLOR_BG_L2}; border-radius: 6px;"
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
            # Right-click on a marker → notify the window.
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
            return  # too-small drag — keep as a click
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
        painter.fillRect(self.rect(), QColor(COLOR_BG_L2))
        painter.setPen(QPen(QColor("#6bb1c9"), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        clip = self.clip
        eff_len = max(1, clip.effective_length_ms)
        mid_y = rect.top() + rect.height() // 2

        # --- waveform ---
        wf = clip.waveform
        if wf is not None and len(wf) > 0:
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
            n = len(wf)
            trim_start_s = clip.trim_start_ms / 1000.0
            half_h = (rect.height() - 10) // 2
            px_per_sec = rect.width() / (eff_len / 1000.0)
            for col_px in range(rect.left() + 2, rect.right() - 1):
                local_ms = (col_px - rect.left()) / max(px_per_sec, 0.001) * 1000.0
                src_s = trim_start_s + local_ms / 1000.0
                bucket = int(src_s * WAVEFORM_BUCKETS_PER_SEC)
                if bucket < 0 or bucket >= n:
                    continue
                peak = float(wf[bucket]) ** 0.7
                h = max(1, int(peak * half_h))
                painter.drawLine(col_px, mid_y - h, col_px, mid_y + h)
        else:
            painter.setPen(QColor(COLOR_TEXT_TERTIARY))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter,
                tr("veditor.sound_editor.waveform_loading"),
            )

        # --- cuts (clip-local ms → rect.x) ---
        for cut in clip.cuts:
            x1 = rect.left() + int(cut.start_ms / eff_len * rect.width())
            x2 = rect.left() + int(cut.end_ms / eff_len * rect.width())
            painter.fillRect(
                x1, rect.top(), max(1, x2 - x1), rect.height(),
                QColor(30, 30, 30, 200),
            )

        # --- fade segments (source-ms → clip-local) ---
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
            painter.fillRect(sel_rect, QColor(55, 138, 221, 80))
            pen = QPen(QColor(COLOR_ACCENT_BLUE))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sel_rect)

        # --- markers (clip._se_markers, source-ms) ---
        markers = getattr(clip, "_se_markers", None) or []
        if markers:
            painter.setPen(Qt.PenStyle.NoPen)
            marker_color = QColor("#5DCAA5")
            for m_ms in markers:
                if m_ms < clip.trim_start_ms or m_ms > clip.effective_trim_end_ms:
                    continue
                mx = self._source_ms_to_x(int(m_ms))
                # Vertical guide line
                painter.setPen(QPen(QColor(93, 202, 165, 140), 1, Qt.PenStyle.DashLine))
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
                pen = QPen(QColor(COLOR_ACCENT_ORANGE))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawLine(px, rect.top(), px, rect.bottom())
                painter.setBrush(QColor(COLOR_ACCENT_ORANGE))
                painter.setPen(QColor("#ff7a4a"))
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


class SoundEditorWindow(QWidget):
    """Knob-based per-clip audio editor (Phase 1/2 of SOUND_EDITOR_SPEC).

    Layout:
        TitleBar
        FileInfo        — filename + duration + cuts/fades counts
        Waveform        — full trimmed peaks + playhead + cut/fade markup
        TabBar          — Basic (live), EQ / Dynamics / Effects / Advanced (placeholders)
        TabContent
            Basic       — 6 knobs (Volume, Pan, Fade In, Fade Out, Speed, Pitch)
                         + action row (Mute, Reverse, Reset All)
                         + preset row
        Transport       — ▶/⏸ + time + 🔊 volume + Apply / Close

    The six Basic-tab knob values flow into the clip (fade_in_ms, fade_out_ms)
    and the track volume slider on the main timeline. Speed / Pitch / Pan are
    stashed on the clip for later wiring into the FFmpeg export filter.
    """

    # Preset definitions (Basic tab). Values match the spec.
    BASIC_PRESETS: dict[str, dict[str, float]] = {
        "Voice Recording": dict(volume=3, pan=0, fade_in=0.1, fade_out=0.3, speed=1.0, pitch=0),
        "Background Music": dict(volume=-6, pan=0, fade_in=1.5, fade_out=2.0, speed=1.0, pitch=0),
        "Game Audio":      dict(volume=0, pan=0, fade_in=0, fade_out=0.2, speed=1.0, pitch=0),
        "Podcast":         dict(volume=2, pan=0, fade_in=0.5, fade_out=0.5, speed=1.0, pitch=0),
    }

    def __init__(self, clip: "AudioClip", parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.clip = clip
        name = clip.display_name or "(unnamed)"
        self.setWindowTitle(tr("veditor.sound_editor.title", name=name))
        self.resize(900, 680)
        self.setStyleSheet(self._qss())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_title_bar(name))
        root.addWidget(self._build_file_info())

        # Waveform section (reuses the existing ClipWaveformView).
        wf_wrap = QWidget()
        wf_wrap.setObjectName("SEWaveformSection")
        wf_layout = QVBoxLayout(wf_wrap)
        wf_layout.setContentsMargins(20, 16, 20, 16)
        self._waveform_view = ClipWaveformView(clip, wf_wrap)
        self._waveform_view.setMinimumHeight(100)
        wf_layout.addWidget(self._waveform_view)
        root.addWidget(wf_wrap)

        root.addWidget(self._build_tab_bar())
        root.addWidget(self._build_tab_content(), stretch=1)
        root.addWidget(self._build_transport())

        # ---- Local playback engine ----
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        self._player_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._player_output)
        if clip.source_path is not None:
            self._player.setSource(QUrl.fromLocalFile(str(clip.source_path)))
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.positionChanged.connect(self._on_player_position)
        self._player_output.setVolume(0.8)
        self._transport_volume_slider.setValue(80)

        # Wire waveform-view signals once all referenced slots exist.
        self._waveform_view.scrub_requested.connect(self._on_waveform_scrub)
        self._waveform_view.selection_changed.connect(self._on_waveform_selection)
        self._waveform_view.selection_cleared.connect(self._on_waveform_selection_cleared)
        self._waveform_view.marker_right_clicked.connect(self._on_marker_right_clicked)

    # -------- QSS --------

    def _qss(self) -> str:
        return f"""
            QWidget {{ background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}
            QWidget#SETitleBar {{
                background-color: {COLOR_BG_L4};
                border-bottom: 1px solid {COLOR_BORDER_DEFAULT};
            }}
            QWidget#SEFileInfo {{
                background-color: #1e1e22;
                border-bottom: 1px solid {COLOR_BG_L4};
            }}
            QWidget#SEWaveformSection {{
                background-color: #0f0f14;
                border-bottom: 1px solid {COLOR_BG_L4};
            }}
            QWidget#SETabBar {{
                background-color: {COLOR_BG_L4};
                border-bottom: 1px solid {COLOR_BORDER_DEFAULT};
            }}
            QPushButton#SETab {{
                background: transparent;
                color: {COLOR_TEXT_TERTIARY};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 18px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton#SETab:hover {{ color: {COLOR_TEXT_SECONDARY}; }}
            QPushButton#SETab:checked {{
                color: {COLOR_ACCENT_BLUE};
                border-bottom: 2px solid {COLOR_ACCENT_BLUE};
            }}
            QWidget#SEContent {{ background-color: {COLOR_BG_L3}; }}
            QWidget#SETransport {{
                background-color: {COLOR_BG_L4};
                border-top: 1px solid {COLOR_BORDER_DEFAULT};
            }}
            QPushButton#SEActionBtn {{
                background-color: {COLOR_BG_L5};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#SEActionBtn:hover {{
                background-color: #44444a;
                border-color: #6a6a72;
            }}
            QPushButton#SEActionBtn:checked {{
                background-color: {COLOR_ACCENT_BLUE};
                border-color: {COLOR_ACCENT_BLUE};
                color: {COLOR_TEXT_PRIMARY};
            }}
            QPushButton#SEPresetBtn {{
                background-color: transparent;
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }}
            QPushButton#SEPresetBtn:hover {{
                background-color: {COLOR_BG_L5};
                color: {COLOR_TEXT_PRIMARY};
                border-color: {COLOR_ACCENT_BLUE};
            }}
            QPushButton#SEPlayBtn {{
                background-color: {COLOR_ACCENT_BLUE};
                color: {COLOR_TEXT_PRIMARY};
                border: none;
                border-radius: 18px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton#SEPlayBtn:hover {{ background-color: {COLOR_ACCENT_BLUE_HOVER}; }}
            QPushButton#SEClose {{
                background-color: {COLOR_BG_L5};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#SEApply {{
                background-color: {COLOR_ACCENT_BLUE};
                color: {COLOR_TEXT_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 700;
            }}
        """

    # -------- section builders --------

    def _build_title_bar(self, name: str) -> QWidget:
        bar = QWidget()
        bar.setObjectName("SETitleBar")
        bar.setFixedHeight(44)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 12, 0)
        icon = QLabel("🎵")
        icon.setStyleSheet("font-size: 16px;")
        title = QLabel(tr("veditor.sound_editor.header"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; font-size: 13px;")
        sub = QLabel(f"— {name}")
        sub.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 12px;")
        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch(1)
        return bar

    def _build_file_info(self) -> QWidget:
        info = QWidget()
        info.setObjectName("SEFileInfo")
        lay = QVBoxLayout(info)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(6)
        name = QLabel(self.clip.display_name or "(unnamed)")
        name.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(name)

        meta_bits: list[str] = []
        if self.clip.duration_ms > 0:
            meta_bits.append(f"⏱ {self.clip.duration_ms / 1000.0:.2f} s")
        meta_bits.append(f"✂ {len(self.clip.cuts)} cuts")
        meta_bits.append(f"⫷ {len(self.clip.fades)} fades")
        if self.clip.source_path is not None:
            meta_bits.append(f"📁 {self.clip.source_path.name}")
        meta = QLabel("   ".join(meta_bits))
        meta.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; font-family: Consolas, monospace;"
        )
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(meta)
        return info

    def _build_tab_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("SETabBar")
        bar.setFixedHeight(42)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)

        from PySide6.QtWidgets import QButtonGroup

        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        tabs = [
            ("basic", tr("veditor.sound_editor.tab.basic")),
            ("eq", tr("veditor.sound_editor.tab.eq")),
            ("dynamics", tr("veditor.sound_editor.tab.dynamics")),
            ("effects", tr("veditor.sound_editor.tab.effects")),
            ("advanced", tr("veditor.sound_editor.tab.advanced")),
        ]
        self._tab_buttons: dict[str, QPushButton] = {}
        for tab_id, tab_label in tabs:
            btn = QPushButton(tab_label)
            btn.setObjectName("SETab")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if tab_id == "basic":
                btn.setChecked(True)
            btn.clicked.connect(lambda _c, t=tab_id: self._switch_tab(t))
            self._tab_group.addButton(btn)
            self._tab_buttons[tab_id] = btn
            lay.addWidget(btn)
        lay.addStretch(1)
        return bar

    def _build_tab_content(self) -> QWidget:
        from PySide6.QtWidgets import QStackedWidget

        self._tab_stack = QStackedWidget()
        self._tab_stack.setObjectName("SEContent")
        self._tab_stack.addWidget(self._build_basic_tab())  # 0
        for tab_id in ("eq", "dynamics", "effects", "advanced"):
            self._tab_stack.addWidget(self._build_placeholder_tab(tab_id))
        return self._tab_stack

    def _build_basic_tab(self) -> QWidget:
        from app.knob_widget import (
            KnobWidget,
            fmt_db, fmt_pan, fmt_seconds, fmt_semitones, fmt_speed,
        )

        c = self.clip
        # Map current clip state into knob starting values.
        init_vol_db = self._track_volume_to_db(self._get_track_volume())
        init_pan = 0.0  # Pan isn't stored yet — starts at center.
        init_fade_in = c.fade_in_ms / 1000.0
        init_fade_out = c.fade_out_ms / 1000.0
        init_speed = getattr(c, "_se_speed", 1.0)
        init_pitch = getattr(c, "_se_pitch", 0.0)

        panel = QWidget()
        panel.setObjectName("SEBasicTab")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        # --- knob grid ---
        knob_row = QHBoxLayout()
        knob_row.setSpacing(12)

        self._knob_volume = KnobWidget(
            label="Volume", value=init_vol_db, minimum=-60, maximum=12,
            default=0, unit="dB", color="blue", formatter=fmt_db,
        )
        self._knob_pan = KnobWidget(
            label="Pan", value=init_pan, minimum=-100, maximum=100,
            default=0, color="green", bipolar=True, formatter=fmt_pan,
        )
        self._knob_fade_in = KnobWidget(
            label="Fade In", value=init_fade_in, minimum=0, maximum=10,
            default=0, unit=" s", color="blue", formatter=fmt_seconds,
        )
        self._knob_fade_out = KnobWidget(
            label="Fade Out", value=init_fade_out, minimum=0, maximum=10,
            default=0, unit=" s", color="blue", formatter=fmt_seconds,
        )
        self._knob_speed = KnobWidget(
            label="Speed", value=init_speed, minimum=0.5, maximum=2.0,
            default=1.0, color="orange", formatter=fmt_speed,
        )
        self._knob_pitch = KnobWidget(
            label="Pitch", value=init_pitch, minimum=-12, maximum=12,
            default=0, unit=" st", color="orange", formatter=fmt_semitones,
        )

        # Wire knobs to live state
        self._knob_volume.valueChanged.connect(self._on_volume_knob)
        self._knob_pan.valueChanged.connect(self._on_pan_knob)
        self._knob_fade_in.valueChanged.connect(self._on_fade_in_knob)
        self._knob_fade_out.valueChanged.connect(self._on_fade_out_knob)
        self._knob_speed.valueChanged.connect(self._on_speed_knob)
        self._knob_pitch.valueChanged.connect(self._on_pitch_knob)

        for k in (
            self._knob_volume, self._knob_pan,
            self._knob_fade_in, self._knob_fade_out,
            self._knob_speed, self._knob_pitch,
        ):
            knob_row.addWidget(k)
        knob_row.addStretch(1)
        root.addLayout(knob_row)

        # --- action buttons ---
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._btn_mute = QPushButton(tr("veditor.sound_editor.basic.mute"))
        self._btn_mute.setObjectName("SEActionBtn")
        self._btn_mute.setCheckable(True)
        self._btn_mute.toggled.connect(self._on_mute_toggled)
        self._btn_reverse = QPushButton(tr("veditor.sound_editor.basic.reverse"))
        self._btn_reverse.setObjectName("SEActionBtn")
        self._btn_reverse.setCheckable(True)
        self._btn_reverse.toggled.connect(
            lambda on: setattr(self.clip, "_se_reverse", on)
        )
        self._btn_reset = QPushButton(tr("veditor.sound_editor.basic.reset_all"))
        self._btn_reset.setObjectName("SEActionBtn")
        self._btn_reset.clicked.connect(self._reset_basic_to_defaults)

        actions.addWidget(self._btn_mute)
        actions.addWidget(self._btn_reverse)
        actions.addSpacing(20)
        actions.addWidget(self._btn_reset)
        actions.addStretch(1)
        root.addLayout(actions)

        # --- presets ---
        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)
        presets_label = QLabel(tr("veditor.sound_editor.basic.presets"))
        presets_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        presets_row.addWidget(presets_label)
        for preset_name in self.BASIC_PRESETS.keys():
            b = QPushButton(preset_name)
            b.setObjectName("SEPresetBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c, n=preset_name: self._apply_preset(n))
            presets_row.addWidget(b)
        presets_row.addStretch(1)
        root.addLayout(presets_row)

        root.addStretch(1)
        return panel

    def _build_placeholder_tab(self, tab_id: str) -> QWidget:
        panel = QWidget()
        panel.setObjectName("SEContent")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 40, 20, 40)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(
            tr(f"veditor.sound_editor.tab.{tab_id}")
        )
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLOR_TEXT_SECONDARY};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note = QLabel(tr("veditor.sound_editor.tab.coming_soon"))
        note.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 12px; padding: 16px;")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)
        lay.addWidget(note)
        lay.addStretch(1)
        return panel

    def _build_transport(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("SETransport")
        bar.setFixedHeight(58)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(8)

        def _mk_icon_btn(symbol: str, tooltip: str, handler) -> QPushButton:
            b = QPushButton(symbol)
            b.setObjectName("SEActionBtn")
            b.setFixedSize(32, 32)
            b.setToolTip(tooltip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(handler)
            return b

        self._prev_marker_btn = _mk_icon_btn(
            "⏮", tr("veditor.sound_editor.tooltip.prev_marker"),
            self._go_to_prev_marker,
        )
        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("SEPlayBtn")
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.clicked.connect(self._toggle_play)
        self._next_marker_btn = _mk_icon_btn(
            "⏭", tr("veditor.sound_editor.tooltip.next_marker"),
            self._go_to_next_marker,
        )
        self._add_marker_btn = _mk_icon_btn(
            "📌", tr("veditor.sound_editor.tooltip.add_marker"),
            self._add_marker_at_playhead,
        )
        self._loop_btn = _mk_icon_btn(
            "🔁", tr("veditor.sound_editor.tooltip.loop"),
            lambda: None,  # replaced below
        )
        self._loop_btn.setCheckable(True)
        # We want toggled state, so replace the clicked handler with
        # a noop and rely on the checked state directly.
        self._loop_btn.clicked.disconnect()

        self._position_label = QLabel("0:00 / 0:00")
        self._position_label.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-family: Consolas, monospace; font-size: 12px;"
        )

        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("font-size: 12px;")
        self._transport_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._transport_volume_slider.setRange(0, 100)
        self._transport_volume_slider.setFixedWidth(100)
        self._transport_volume_slider.valueChanged.connect(
            lambda v: self._player_output.setVolume(max(0.0, min(1.0, v / 100.0)))
        )

        self._apply_btn = QPushButton(tr("veditor.sound_editor.apply"))
        self._apply_btn.setObjectName("SEApply")
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.clicked.connect(self._apply_and_close)

        self._close_btn = QPushButton(tr("veditor.sound_editor.close"))
        self._close_btn.setObjectName("SEClose")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.close)

        lay.addWidget(self._prev_marker_btn)
        lay.addWidget(self._play_btn)
        lay.addWidget(self._next_marker_btn)
        lay.addSpacing(6)
        lay.addWidget(self._add_marker_btn)
        lay.addWidget(self._loop_btn)
        lay.addSpacing(10)
        lay.addWidget(self._position_label)
        lay.addStretch(1)
        lay.addWidget(vol_icon)
        lay.addWidget(self._transport_volume_slider)
        lay.addSpacing(14)
        lay.addWidget(self._close_btn)
        lay.addWidget(self._apply_btn)

        # --- keyboard shortcuts (scoped to this window) ---
        from PySide6.QtGui import QKeySequence, QShortcut
        for key, handler in (
            ("Space", self._toggle_play),
            ("M",     self._add_marker_at_playhead),
            ("L",     lambda: self._loop_btn.setChecked(not self._loop_btn.isChecked())),
            (",",     self._go_to_prev_marker),
            (".",     self._go_to_next_marker),
        ):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(handler)

        return bar

    # -------- state plumbing --------

    def _get_track_volume(self) -> float:
        """Find the parent AudioTrack's master volume, fall back to 1.0."""
        parent = self.parent()
        if parent is not None:
            tracks = getattr(parent, "_audio_tracks", None) or []
            for t in tracks:
                if self.clip in t.clips:
                    return float(t.volume)
        return 1.0

    def _set_track_volume(self, vol_linear: float) -> None:
        parent = self.parent()
        if parent is None:
            return
        tracks = getattr(parent, "_audio_tracks", None) or []
        for t in tracks:
            if self.clip in t.clips:
                t.volume = float(vol_linear)
                # Update the row's slider + mixer.
                row = parent._audio_rows.get(t.id)
                if row is not None:
                    with _block_signals(row._volume_slider):
                        row._volume_slider.setValue(int(round(t.volume * 100)))
                parent._audio_mixer.update_track(t)
                break

    @staticmethod
    def _track_volume_to_db(vol_linear: float) -> float:
        """Convert linear gain (0..1.5) to dB for UI display."""
        if vol_linear <= 0.0:
            return -60.0
        return max(-60.0, 20.0 * math.log10(vol_linear))

    @staticmethod
    def _db_to_track_volume(db: float) -> float:
        if db <= -60.0:
            return 0.0
        return 10.0 ** (db / 20.0)

    def _switch_tab(self, tab_id: str) -> None:
        idx = {"basic": 0, "eq": 1, "dynamics": 2, "effects": 3, "advanced": 4}.get(tab_id, 0)
        self._tab_stack.setCurrentIndex(idx)
        # Sync checked state (QButtonGroup should handle, but be defensive).
        for tid, btn in self._tab_buttons.items():
            btn.setChecked(tid == tab_id)

    # -------- knob handlers --------

    def _on_volume_knob(self, db: float) -> None:
        # Main timeline + export use the track's linear volume.
        linear = self._db_to_track_volume(db)
        self._set_track_volume(linear)
        # Local preview: drive the editor's own player output so the
        # user hears the change immediately. The local master (the
        # transport 🔊 slider) multiplies on top, so we cap at 1.0
        # here — the slider can still attenuate further.
        try:
            self._player_output.setVolume(max(0.0, min(1.0, linear)))
        except Exception:
            pass

    def _on_pan_knob(self, pan: float) -> None:
        # Pan is captured on the clip for FFmpeg export. Qt's
        # QMediaPlayer / QAudioOutput doesn't expose a built-in
        # pan, so local preview stays centered — fine for v1.
        self.clip._se_pan = pan

    def _on_fade_in_knob(self, sec: float) -> None:
        self.clip.fade_in_ms = int(round(sec * 1000))
        self._refresh_timeline_row()
        self._waveform_view.refresh()

    def _on_fade_out_knob(self, sec: float) -> None:
        self.clip.fade_out_ms = int(round(sec * 1000))
        self._refresh_timeline_row()
        self._waveform_view.refresh()

    def _on_speed_knob(self, rate: float) -> None:
        self.clip._se_speed = rate
        # QMediaPlayer supports playbackRate natively — let the
        # local preview respond immediately to the Speed knob.
        try:
            self._player.setPlaybackRate(float(rate))
        except Exception:
            pass

    def _on_pitch_knob(self, semitones: float) -> None:
        # Real-time pitch shifting isn't available in QMediaPlayer; the
        # value is stashed for FFmpeg export (`asetrate` + `atempo` chain).
        # No audible local preview change for now.
        self.clip._se_pitch = semitones

    def _on_mute_toggled(self, muted: bool) -> None:
        # Implement mute as a volume-knob override: record the current
        # volume, swap to silence, and restore on un-mute.
        if muted:
            self._muted_restore_db = self._knob_volume.value()
            self._knob_volume.setValue(-60.0)
        else:
            restore = getattr(self, "_muted_restore_db", 0.0)
            self._knob_volume.setValue(restore)

    def _reset_basic_to_defaults(self) -> None:
        self._knob_volume.setValue(0.0)
        self._knob_pan.setValue(0.0)
        self._knob_fade_in.setValue(0.0)
        self._knob_fade_out.setValue(0.0)
        self._knob_speed.setValue(1.0)
        self._knob_pitch.setValue(0.0)
        self._btn_mute.setChecked(False)
        self._btn_reverse.setChecked(False)

    def _apply_preset(self, name: str) -> None:
        preset = self.BASIC_PRESETS.get(name)
        if preset is None:
            return
        self._knob_volume.setValue(preset["volume"])
        self._knob_pan.setValue(preset["pan"])
        self._knob_fade_in.setValue(preset["fade_in"])
        self._knob_fade_out.setValue(preset["fade_out"])
        self._knob_speed.setValue(preset["speed"])
        self._knob_pitch.setValue(preset["pitch"])

    # -------- transport --------

    def _toggle_play(self) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_player_position(self, pos_ms: int) -> None:
        dur = self._player.duration() or self.clip.duration_ms
        self._position_label.setText(
            f"{_format_ms(int(pos_ms))} / {_format_ms(int(dur))}"
        )
        self._waveform_view.set_playhead_source_ms(int(pos_ms))
        # Loop handling: if loop is on AND a selection exists, wrap the
        # playhead back to the selection start whenever it crosses the
        # selection end. Uses the waveform view's selection as the
        # single source of truth.
        if self._loop_btn.isChecked():
            sel = self._waveform_view.selection()
            if sel is not None and pos_ms >= sel[1]:
                try:
                    self._player.setPosition(int(sel[0]))
                except Exception:
                    pass

    def _on_playback_state(self, state) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("⏸")
        else:
            self._play_btn.setText("▶")
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self._waveform_view.clear_playhead()

    # -------- markers + selection + loop --------

    def _markers(self) -> list[int]:
        if not hasattr(self.clip, "_se_markers") or self.clip._se_markers is None:
            self.clip._se_markers = []
        return self.clip._se_markers

    def _add_marker_at_playhead(self) -> None:
        pos = self._player.position()
        if pos <= 0:
            return
        # Dedup within 50 ms so repeated 'M' presses don't stack.
        markers = self._markers()
        for m in markers:
            if abs(m - pos) < 50:
                return
        markers.append(int(pos))
        markers.sort()
        self._waveform_view.refresh()

    def _go_to_prev_marker(self) -> None:
        markers = self._markers()
        if not markers:
            return
        pos = self._player.position()
        # Previous marker = the latest one strictly before pos (minus a
        # small epsilon so hitting ⏮ twice in a row actually jumps back).
        target = None
        for m in markers:
            if m < pos - 200:
                target = m
        if target is None:
            target = markers[0]
        self._player.setPosition(int(target))

    def _go_to_next_marker(self) -> None:
        markers = self._markers()
        if not markers:
            return
        pos = self._player.position()
        for m in markers:
            if m > pos + 50:
                self._player.setPosition(int(m))
                return

    def _on_waveform_scrub(self, source_ms: int) -> None:
        # QMediaPlayer position is source-ms (absolute within the file).
        try:
            self._player.setPosition(int(source_ms))
        except Exception:
            pass

    def _on_waveform_selection(self, start_ms: int, end_ms: int) -> None:
        # Park the selection on the clip so the loop logic + future
        # clip-range effects (e.g. "apply EQ to selection") can read it.
        self.clip.selection_start_ms = max(0, int(start_ms) - self.clip.trim_start_ms)
        self.clip.selection_end_ms = max(0, int(end_ms) - self.clip.trim_start_ms)

    def _on_waveform_selection_cleared(self) -> None:
        self.clip.selection_start_ms = -1
        self.clip.selection_end_ms = -1

    def _on_marker_right_clicked(self, idx: int, global_pos: QPoint) -> None:
        markers = self._markers()
        if idx < 0 or idx >= len(markers):
            return
        menu = QMenu(self)
        act_delete = menu.addAction(tr("veditor.sound_editor.marker.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_delete:
            del markers[idx]
            self._waveform_view.refresh()

    def _apply_and_close(self) -> None:
        # All knob mutations already flow live; "Apply" is effectively
        # the same as "Close" today. Left as a separate button so the
        # upcoming effects tabs (which stage changes) have somewhere to
        # hook into.
        self._refresh_timeline_row()
        self.close()

    def _refresh_timeline_row(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        for t in getattr(parent, "_audio_tracks", None) or []:
            if self.clip in t.clips:
                row = parent._audio_rows.get(t.id)
                if row is not None:
                    row.update()
                parent._audio_mixer.update_track(t)
                break

    def refresh_waveform(self) -> None:
        self._waveform_view.refresh()

    def closeEvent(self, event) -> None:
        try:
            self._player.stop()
            self._player.setSource(QUrl())
        except Exception:
            pass
        super().closeEvent(event)


class PreviewPopoutWindow(QWidget):
    """Top-level mirror of the preview area. Displays the latest frame
    coming from ``ProjectPlayer.frame_ready`` scaled to fit. Closing
    this window simply destroys it — the in-editor preview was never
    disturbed, so editing keeps working the whole time.
    """

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("veditor.popout.title"))
        self.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG_L1}; }}"
        )
        self.resize(960, 540)
        self.setMinimumSize(320, 180)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self._last_image: QImage | None = None
        self._last_pixmap: QPixmap | None = None

    def update_frame(self, image: QImage) -> None:
        self._last_image = image
        self._rescale()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._last_image is None:
            return
        target = self._label.size()
        if target.width() < 2 or target.height() < 2:
            return
        pm = QPixmap.fromImage(self._last_image).scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._last_pixmap = pm
        self._label.setPixmap(pm)

    def keyPressEvent(self, event) -> None:
        # F11 toggles fullscreen on the popout monitor; Esc leaves it.
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)


class AudioTrackRow(QWidget):
    """Multi-clip timeline row for an ``AudioTrack``.

    One row = one AudioTrack. Multiple AudioClips belonging to that
    track are drawn side-by-side on the bar area; each can be dragged,
    selected, faded, and split independently.

    The row header shows the track's master volume slider. Per-clip
    interactions (drag / selection / fade / context menu / double-click
    for sound editor) target the clip the user actually clicks on.
    """

    clicked = Signal(int)                 # track_id
    volume_changed = Signal(int, float)   # track_id, master volume
    row_context_menu = Signal(int, QPoint)   # track_id, global_pos (clicked on empty area)
    clip_context_menu = Signal(int, int, QPoint)  # track_id, clip_id, global_pos
    load_source_requested = Signal(int)   # track_id — empty-row click
    media_dropped = Signal(int, object)   # track_id, Path — any media for routing
    track_changed = Signal(int)           # track_id — clips were mutated
    clip_selection_changed = Signal(int, int, int, int)  # track_id, clip_id, start, end
    open_editor_requested = Signal(int, int)  # track_id, clip_id

    MARGIN = 10
    LABEL_H = 22
    BAR_H = 48
    PADDING = 8

    BAR_COLOR = QColor("#3e6a7e")          # teal-ish for audio
    BAR_BORDER = QColor("#6bb1c9")
    BAR_COLOR_EMPTY = QColor("#2a2a32")
    BAR_COLOR_ACTIVE = QColor("#4a86a0")

    FADE_EDGE_GRAB_PX = 6

    def __init__(self, track: AudioTrack) -> None:
        super().__init__()
        self.track = track
        self._is_active: bool = False
        self._active_clip_id: int | None = None
        self._position_ms: int = 0
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        # Active interaction state. ``_interaction_clip`` points to the
        # AudioClip the user is currently manipulating (drag / select /
        # fade-resize); cleared on mouse release.
        self._interaction_clip: AudioClip | None = None
        self._dragging_offset: bool = False
        self._dragging_selection: bool = False
        self._drag_start_x: int = 0
        self._drag_start_local_ms: int = 0
        self._drag_start_offset_ms: int = 0
        self._resizing_fade: FadeSegment | None = None
        self._resize_side: str = ""
        self._resize_orig_start: int = 0
        self._resize_orig_end: int = 0
        self._waveform_errors: dict[int, str] = {}  # clip_id → reason

        self.setFixedHeight(self.LABEL_H + self.BAR_H + self.PADDING)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAcceptDrops(True)

        self._name_label = QLabel(track.display_name or tr("veditor.audio.track_empty"), self)
        self._name_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-weight: 600; font-size: 11px; background: transparent;"
        )
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._volume_slider.setMinimum(0)
        self._volume_slider.setMaximum(150)
        self._volume_slider.setValue(int(round(track.volume * 100)))
        self._volume_slider.setFixedWidth(110)
        self._volume_slider.setToolTip(tr("veditor.audio.volume"))
        self._volume_slider.valueChanged.connect(self._on_volume_slider_changed)

        self._reposition_header()

    # ---- geometry / state helpers ----

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self.update()

    def set_active(self, active: bool) -> None:
        if self._is_active == active:
            return
        self._is_active = active
        self.update()

    def set_position(self, ms: int) -> None:
        self._position_ms = max(0, int(ms))
        self.update()

    def refresh_from_track(self) -> None:
        self._name_label.setText(self.track.display_name or tr("veditor.audio.track_empty"))
        with _block_signals(self._volume_slider):
            self._volume_slider.setValue(int(round(self.track.volume * 100)))
        self.update()

    def set_waveform_error(self, clip_id: int, reason: str) -> None:
        self._waveform_errors[clip_id] = reason or "decode failed"
        self.update()

    def clear_waveform_error(self, clip_id: int) -> None:
        self._waveform_errors.pop(clip_id, None)

    def _preferred_width(self) -> int:
        span = self.track.extent_ms()
        return int(span / 1000.0 * self._px_per_sec) + 2 * self.MARGIN + 40

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_header()

    def _reposition_header(self) -> None:
        self._name_label.setGeometry(
            self.MARGIN, 3,
            max(50, self.width() - self._volume_slider.width() - self.MARGIN * 3),
            self.LABEL_H - 4,
        )
        self._volume_slider.setGeometry(
            self.width() - self._volume_slider.width() - self.MARGIN,
            (self.LABEL_H - self._volume_slider.sizeHint().height()) // 2,
            self._volume_slider.width(),
            self._volume_slider.sizeHint().height(),
        )

    def _project_ms_to_x(self, ms: int) -> int:
        return int(self.MARGIN + ms / 1000.0 * self._px_per_sec)

    def _x_to_project_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    # ---- per-clip hit testing ----

    def _clip_bar_rect(self, clip: AudioClip) -> QRect:
        bar_y = self.LABEL_H
        x1 = self._project_ms_to_x(clip.offset_ms)
        x2 = self._project_ms_to_x(clip.offset_ms + clip.effective_length_ms)
        return QRect(x1, bar_y + 4, max(2, x2 - x1), self.BAR_H - 8)

    def _clip_at_pos(self, pos: QPoint) -> AudioClip | None:
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.BAR_H:
            return None
        for clip in self.track.clips:
            if clip.source_path is None:
                continue
            r = self._clip_bar_rect(clip)
            if r.left() <= pos.x() <= r.right():
                return clip
        return None

    def _x_to_clip_local_ms(self, clip: AudioClip, x: int) -> int:
        project_ms = self._x_to_project_ms(x)
        local = project_ms - clip.offset_ms
        return max(0, min(clip.effective_length_ms, local))

    def _clip_local_ms_to_x(self, clip: AudioClip, local_ms: int) -> int:
        return self._project_ms_to_x(clip.offset_ms + local_ms)

    def _fade_edge_at(self, clip: AudioClip, x: int, y: int):
        bar_y = self.LABEL_H
        if y < bar_y or y > bar_y + self.BAR_H:
            return None, ""
        for fade in clip.fades:
            local_start = fade.start_ms - clip.trim_start_ms
            local_end = fade.end_ms - clip.trim_start_ms
            fx1 = self._clip_local_ms_to_x(clip, local_start)
            fx2 = self._clip_local_ms_to_x(clip, local_end)
            if abs(x - fx1) <= self.FADE_EDGE_GRAB_PX:
                return fade, "left"
            if abs(x - fx2) <= self.FADE_EDGE_GRAB_PX:
                return fade, "right"
        return None, ""

    def _fade_under(self, clip: AudioClip, pos: QPoint):
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.BAR_H:
            return None
        local_ms = self._x_to_clip_local_ms(clip, pos.x())
        source_ms = clip.trim_start_ms + local_ms
        for fade in clip.fades:
            if fade.start_ms <= source_ms < fade.end_ms:
                return fade
        return None

    # ---- mouse ----

    def _on_volume_slider_changed(self, value: int) -> None:
        vol = max(0.0, min(1.5, value / 100.0))
        self.track.volume = vol
        self.volume_changed.emit(self.track.id, vol)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        x = pos.x()
        y = pos.y()
        mods = event.modifiers()

        # Right-click dispatches to fade menu / clip menu / row menu.
        if event.button() == Qt.MouseButton.RightButton:
            clip = self._clip_at_pos(pos)
            if clip is not None:
                fade = self._fade_under(clip, pos)
                if fade is not None:
                    self._show_fade_menu(clip, fade, event.globalPosition().toPoint())
                    return
                self.clip_context_menu.emit(
                    self.track.id, clip.id, event.globalPosition().toPoint()
                )
                return
            self.row_context_menu.emit(self.track.id, event.globalPosition().toPoint())
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.clicked.emit(self.track.id)
        if y < self.LABEL_H:
            return

        # Empty row → request to load an audio file.
        if not self.track.is_loaded:
            self.load_source_requested.emit(self.track.id)
            return

        clip = self._clip_at_pos(pos)
        if clip is None:
            # Clicked on empty bar area between clips → nothing to do.
            return
        self._active_clip_id = clip.id
        self._interaction_clip = clip

        # 1. Fade edge resize takes priority.
        fade, side = self._fade_edge_at(clip, x, y)
        if fade is not None:
            self._resizing_fade = fade
            self._resize_side = side
            self._resize_orig_start = fade.start_ms
            self._resize_orig_end = fade.end_ms
            self._drag_start_x = x
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        # 2. Shift+drag = range select on this clip (clip-local ms).
        if mods & Qt.KeyboardModifier.ShiftModifier:
            ms = self._x_to_clip_local_ms(clip, x)
            self._dragging_selection = True
            self._drag_start_local_ms = ms
            clip.selection_start_ms = ms
            clip.selection_end_ms = ms
            # Clear selection on other clips for sanity.
            for c in self.track.clips:
                if c is not clip:
                    c.selection_start_ms = -1
                    c.selection_end_ms = -1
            self.update()
            self.clip_selection_changed.emit(self.track.id, clip.id, ms, ms)
            return

        # 3. Else drag the clip on the project timeline.
        self._dragging_offset = True
        self._drag_start_x = x
        self._drag_start_offset_ms = clip.offset_ms
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        x = pos.x()
        clip = self._interaction_clip

        if self._resizing_fade is not None and clip is not None:
            delta_ms = int((x - self._drag_start_x) / max(self._px_per_sec, 0.001) * 1000)
            fade = self._resizing_fade
            # Fade start/end are in source-ms (absolute within the source
            # file), so their valid range is [clip.trim_start_ms, clip.effective_trim_end_ms].
            if self._resize_side == "left":
                new_start = max(
                    clip.trim_start_ms,
                    min(fade.end_ms - 100, self._resize_orig_start + delta_ms),
                )
                fade.start_ms = new_start
            else:
                new_end = min(
                    clip.effective_trim_end_ms,
                    max(fade.start_ms + 100, self._resize_orig_end + delta_ms),
                )
                fade.end_ms = new_end
            self.update()
            self.track_changed.emit(self.track.id)
            return

        if self._dragging_selection and clip is not None:
            ms = self._x_to_clip_local_ms(clip, x)
            start = min(self._drag_start_local_ms, ms)
            end = max(self._drag_start_local_ms, ms)
            clip.selection_start_ms = start
            clip.selection_end_ms = end
            self.update()
            self.clip_selection_changed.emit(self.track.id, clip.id, start, end)
            return

        if self._dragging_offset and clip is not None:
            dx = x - self._drag_start_x
            d_ms = int(dx / max(self._px_per_sec, 0.001) * 1000)
            new_offset = max(0, self._drag_start_offset_ms + d_ms)
            if new_offset != clip.offset_ms:
                clip.offset_ms = new_offset
                self.track_changed.emit(self.track.id)
                self.update()
            return

        # Idle hover: cursor hinting.
        hover_clip = self._clip_at_pos(pos)
        if hover_clip is not None:
            fade, _side = self._fade_edge_at(hover_clip, x, pos.y())
            if fade is not None:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                return
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging_offset = False
        self._dragging_selection = False
        self._resizing_fade = None
        self._resize_side = ""
        self._interaction_clip = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        pos = event.position().toPoint()
        clip = self._clip_at_pos(pos)
        if clip is None:
            return
        # Double-click on a fade → delete that fade.
        fade = self._fade_under(clip, pos)
        if fade is not None:
            try:
                clip.fades.remove(fade)
            except ValueError:
                return
            self.update()
            self.track_changed.emit(self.track.id)
            return
        # Else open the sound editor for this clip.
        self.open_editor_requested.emit(self.track.id, clip.id)

    # ---- drag & drop ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        md = event.mimeData()
        if md.hasFormat(FADE_MIME_TYPE):
            event.acceptProposedAction()
            return
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_audio_path(p) or is_video_path(p):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        pos = event.position().toPoint()

        if md.hasFormat(FADE_MIME_TYPE):
            clip = self._clip_at_pos(pos)
            if clip is None or clip.source_path is None or clip.effective_length_ms <= 0:
                event.ignore()
                return
            try:
                dur_ms = int(bytes(md.data(FADE_MIME_TYPE)).decode("utf-8"))
            except Exception:
                dur_ms = FadeCard.DEFAULT_DURATION_MS
            dur_ms = max(100, dur_ms)
            center_local = self._x_to_clip_local_ms(clip, pos.x())
            # FadeSegments are stored in source-ms (absolute within
            # source file) so they survive trim / split correctly.
            source_center = clip.trim_start_ms + center_local
            start = max(clip.trim_start_ms, source_center - dur_ms // 2)
            end = min(clip.effective_trim_end_ms, start + dur_ms)
            if end <= start:
                event.ignore()
                return
            clip.fades.append(FadeSegment(start, end))
            clip.fades.sort(key=lambda f: f.start_ms)
            self.update()
            self.track_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return

        if not md.hasUrls():
            event.ignore()
            return
        for u in md.urls():
            p = Path(u.toLocalFile())
            if is_audio_path(p) or is_video_path(p):
                self.media_dropped.emit(self.track.id, p)
                event.acceptProposedAction()
                return
        event.ignore()

    # ---- fade menu (per-fade, on right-click) ----

    def _show_fade_menu(self, clip: AudioClip, fade, global_pos) -> None:
        menu = QMenu(self)
        act_in = menu.addAction(tr("veditor.fade_menu.in"))
        act_in.setCheckable(True)
        act_in.setChecked(getattr(fade, "kind", "both") == "in")
        act_out = menu.addAction(tr("veditor.fade_menu.out"))
        act_out.setCheckable(True)
        act_out.setChecked(getattr(fade, "kind", "both") == "out")
        act_both = menu.addAction(tr("veditor.fade_menu.both"))
        act_both.setCheckable(True)
        act_both.setChecked(getattr(fade, "kind", "both") == "both")
        menu.addSeparator()
        act_del = menu.addAction(tr("veditor.fade_menu.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_in:
            fade.kind = "in"
        elif chosen is act_out:
            fade.kind = "out"
        elif chosen is act_both:
            fade.kind = "both"
        elif chosen is act_del:
            try:
                clip.fades.remove(fade)
            except ValueError:
                pass
        else:
            return
        self.update()
        self.track_changed.emit(self.track.id)

    # ---- paint ----

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Header bg
        if self._is_active:
            painter.fillRect(0, 0, self.width(), self.LABEL_H, QColor(COLOR_BG_L5))
        else:
            painter.fillRect(0, 0, self.width(), self.LABEL_H, QColor(COLOR_BG_L3))
        # Bar area bg
        bar_y = self.LABEL_H
        painter.fillRect(0, bar_y, self.width(), self.BAR_H, QColor(COLOR_BG_L2))

        track = self.track
        if not track.is_loaded:
            painter.setPen(QPen(QColor(COLOR_BORDER_DEFAULT), 1, Qt.PenStyle.DashLine))
            rect = QRect(self.MARGIN, bar_y + 4, self.width() - 2 * self.MARGIN, self.BAR_H - 8)
            painter.drawRect(rect)
            painter.setPen(QColor(COLOR_TEXT_TERTIARY))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, tr("veditor.audio.drop_hint")
            )
            return

        # Each clip renders independently.
        for clip in track.clips:
            if clip.source_path is None:
                continue
            self._paint_clip(painter, clip)

        # Playhead spans the whole row.
        px = self._project_ms_to_x(self._position_ms)
        pen = QPen(QColor(COLOR_ACCENT_ORANGE))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(px, bar_y, px, bar_y + self.BAR_H)

    def _paint_clip(self, painter: QPainter, clip: AudioClip) -> None:
        bar_rect = self._clip_bar_rect(clip)
        is_active_clip = (clip.id == self._active_clip_id)
        color = self.BAR_COLOR_ACTIVE if is_active_clip else self.BAR_COLOR
        painter.fillRect(bar_rect, color)
        painter.setPen(QPen(self.BAR_BORDER, 1))
        painter.drawRect(bar_rect)

        # Waveform
        mid_y = bar_rect.top() + bar_rect.height() // 2
        wf = clip.waveform
        err = self._waveform_errors.get(clip.id)
        if wf is not None and len(wf) > 0:
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
            painter.setPen(QPen(QColor(255, 255, 255, 210), 1))
            n = len(wf)
            trim_start_s = clip.trim_start_ms / 1000.0
            half_h = (bar_rect.height() - 2) // 2
            for col_px in range(bar_rect.left() + 2, bar_rect.right() - 1):
                local_ms = (col_px - bar_rect.left()) / max(self._px_per_sec, 0.001) * 1000.0
                src_s = trim_start_s + local_ms / 1000.0
                bucket = int(src_s * WAVEFORM_BUCKETS_PER_SEC)
                if bucket < 0 or bucket >= n:
                    continue
                peak = float(wf[bucket]) ** 0.7
                h = max(1, int(peak * half_h))
                painter.drawLine(col_px, mid_y - h, col_px, mid_y + h)
        elif err:
            painter.setPen(QPen(QColor(200, 80, 80, 200), 1, Qt.PenStyle.DashLine))
            painter.drawLine(bar_rect.left() + 3, mid_y, bar_rect.right() - 3, mid_y)
            painter.setPen(QColor(230, 140, 140, 230))
            f = painter.font(); f.setPixelSize(10); f.setBold(True); painter.setFont(f)
            painter.drawText(
                bar_rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignCenter,
                "⚠ decode failed",
            )
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
            painter.drawLine(bar_rect.left() + 3, mid_y, bar_rect.right() - 3, mid_y)

        # Filename on the bar
        painter.setPen(QColor(255, 255, 255, 230))
        f = painter.font(); f.setPixelSize(10); f.setBold(False); painter.setFont(f)
        painter.drawText(
            bar_rect.adjusted(6, 0, -6, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            clip.display_name,
        )

        # Cuts — clip-local ms domain, dark overlay.
        for cut in clip.cuts:
            cx1 = self._clip_local_ms_to_x(clip, cut.start_ms)
            cx2 = self._clip_local_ms_to_x(clip, cut.end_ms)
            cut_rect = QRect(cx1, bar_rect.top(), max(1, cx2 - cx1), bar_rect.height())
            painter.fillRect(cut_rect, QColor(30, 30, 30, 210))
            if cut_rect.width() > 24:
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(cut_rect, Qt.AlignmentFlag.AlignCenter, tr("veditor.cut_label"))

        # FadeSegment actors — in source-ms domain.
        for fade in clip.fades:
            self._paint_fade_segment(painter, clip, fade, bar_rect)

        # Selection (clip-local ms).
        if clip.selection_start_ms >= 0 and clip.selection_end_ms > clip.selection_start_ms:
            sx1 = self._clip_local_ms_to_x(clip, clip.selection_start_ms)
            sx2 = self._clip_local_ms_to_x(clip, clip.selection_end_ms)
            sel_rect = QRect(sx1, bar_rect.top(), max(1, sx2 - sx1), bar_rect.height())
            painter.fillRect(sel_rect, QColor(55, 138, 221, 80))
            pen = QPen(QColor(COLOR_ACCENT_BLUE)); pen.setWidth(2)
            painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sel_rect)

    def _paint_fade_segment(self, painter: QPainter, clip: AudioClip, fade, bar_rect: QRect) -> None:
        local_start = fade.start_ms - clip.trim_start_ms
        local_end = fade.end_ms - clip.trim_start_ms
        fx1 = self._clip_local_ms_to_x(clip, local_start)
        fx2 = self._clip_local_ms_to_x(clip, local_end)
        if fx2 <= fx1:
            return
        kind = getattr(fade, "kind", "both")
        painter.save()
        painter.setClipRect(bar_rect)
        if kind == "in":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 220))
            g.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(fx1, bar_rect.top(), fx2 - fx1, bar_rect.height(), g)
        elif kind == "out":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(216, 90, 48, 0))
            g.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, bar_rect.top(), fx2 - fx1, bar_rect.height(), g)
        else:
            mid = (fx1 + fx2) // 2
            g_out = QLinearGradient(fx1, 0, mid, 0)
            g_out.setColorAt(0.0, QColor(216, 90, 48, 0))
            g_out.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, bar_rect.top(), mid - fx1, bar_rect.height(), g_out)
            g_in = QLinearGradient(mid, 0, fx2, 0)
            g_in.setColorAt(0.0, QColor(0, 0, 0, 220))
            g_in.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(mid, bar_rect.top(), fx2 - mid, bar_rect.height(), g_in)
        painter.restore()
        pen = QPen(QColor(COLOR_ACCENT_ORANGE)); pen.setWidth(2)
        painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(fx1, bar_rect.top(), max(1, fx2 - fx1), bar_rect.height())
        hw = 3; hc = QColor(255, 150, 80)
        painter.fillRect(fx1 - hw // 2, bar_rect.top(), hw, bar_rect.height(), hc)
        painter.fillRect(fx2 - hw // 2, bar_rect.top(), hw, bar_rect.height(), hc)


class _block_signals:
    """Context manager — blocks Qt signals on the given object."""
    def __init__(self, obj):
        self._obj = obj
    def __enter__(self):
        self._prev = self._obj.blockSignals(True)
        return self._obj
    def __exit__(self, *exc):
        self._obj.blockSignals(self._prev)


class VideoEditorWindow(QWidget):
    """Professional video editor with multi-track timeline, per-region speed
    (0.25x ~ 16x), cut regions, thumbnails, and right-click context menus.

    Playback model (v1): one active track plays in the preview at a time.
    Switch between tracks by clicking a track row.
    """

    def __init__(self, source_path: Path | None = None) -> None:
        super().__init__()
        self._tracks: list[VideoTrack] = []
        self._track_rows: dict[int, TrackRow] = {}
        self._audio_tracks: list[AudioTrack] = []
        self._audio_rows: dict[int, AudioTrackRow] = {}
        self._waveform_extractors: dict[int, WaveformExtractor] = {}
        self._preview_popout: "PreviewPopoutWindow | None" = None
        self._next_track_id: int = 1
        self._active_track_id: int | None = None
        self._current_segment_speed: float = 1.0
        self._extractors: dict[int, ThumbnailExtractor] = {}
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        self._strokes: list[Stroke] = []
        self._bubbles: list[SpeechBubble] = []
        self._bubble_items: list[SpeechBubbleItem] = []

        self.setObjectName("EditorRoot")
        self.setWindowTitle(tr("veditor.title"))
        self.resize(1180, 780)
        self.setStyleSheet(VIDEO_EDITOR_EXTRA_QSS)
        # Accept dropped files anywhere on the editor — drop on a track
        # row targets that row; drop on empty area creates a new track.
        self.setAcceptDrops(True)

        self._player = ProjectPlayer(self)
        self._player.frame_ready.connect(self._on_frame_ready)
        self._player.position_changed.connect(self._on_position_changed)
        self._player.duration_changed.connect(self._on_duration_changed)
        self._player.state_changed.connect(self._on_playback_state_changed)
        self._player.error_occurred.connect(self._on_player_error)

        # Audio mixer — listens to the project player and keeps each
        # audio track's QMediaPlayer in sync.
        self._audio_mixer = AudioMixer(self)
        self._player.state_changed.connect(self._audio_mixer.on_state_changed)
        self._player.position_changed.connect(self._audio_mixer.on_position_changed)

        self._build_ui()

        if source_path is not None:
            self._add_track_with_source(Path(source_path))
        else:
            self._add_empty_track()

    # ------------------------- UI --------------------------

    @staticmethod
    def _make_section_header(title: str, accent: str) -> QLabel:
        label = QLabel(title.upper())
        label.setProperty("sectionHeader", "true")
        label.setProperty("accent", accent)  # preview / timeline / subtitles
        return label

    def _build_fade_card(self) -> QWidget:
        self.fade_card = FadeCard()
        return self.fade_card

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(8)

        # --- Top toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.add_track_btn = QPushButton(tr("veditor.btn.add_track"))
        self.add_track_btn.setObjectName("ToolButton")
        self.add_track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_track_btn.clicked.connect(self._add_empty_track)

        self.del_track_btn = QPushButton(tr("veditor.btn.del_track"))
        self.del_track_btn.setObjectName("ToolButton")
        self.del_track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_track_btn.clicked.connect(self._delete_active_track)

        self.add_audio_btn = QPushButton(tr("veditor.btn.add_audio"))
        self.add_audio_btn.setObjectName("ToolButton")
        self.add_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_audio_btn.setToolTip(tr("veditor.audio.add_hint"))
        self.add_audio_btn.clicked.connect(self._add_empty_audio_track)

        self.reset_btn = QPushButton(tr("veditor.btn.reset"))
        self.reset_btn.setObjectName("ToolButton")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.clicked.connect(self._on_reset_active_track)

        self.export_btn = QPushButton(tr("veditor.btn.export"))
        self.export_btn.setObjectName("PrimaryToolButton")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._on_export)

        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setObjectName("ToolButton")
        self.zoom_out_btn.setFixedWidth(32)
        self.zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_out_btn.clicked.connect(lambda: self._change_zoom(0.6667))

        self.zoom_label = QLabel(self._format_zoom())
        self.zoom_label.setObjectName("ZoomLabel")
        self.zoom_label.setFixedWidth(70)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setObjectName("ToolButton")
        self.zoom_in_btn.setFixedWidth(32)
        self.zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_in_btn.clicked.connect(lambda: self._change_zoom(1.5))

        self.zoom_fit_btn = QPushButton(tr("veditor.btn.zoom_fit"))
        self.zoom_fit_btn.setObjectName("ToolButton")
        self.zoom_fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_fit_btn.clicked.connect(self._zoom_fit)

        # Pop-out icon is shown inside the PREVIEW section header (right
        # end) rather than here, so that it reads as "this control
        # belongs to the preview". Created eagerly so _build_preview_header
        # can reference it, attached there.
        self.popout_btn = QPushButton("⛶")
        self.popout_btn.setObjectName("PreviewPopoutIcon")
        self.popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popout_btn.setToolTip(tr("veditor.popout.tooltip"))
        self.popout_btn.setFixedSize(28, 24)
        self.popout_btn.clicked.connect(self._toggle_preview_popout)

        toolbar.addWidget(self.reset_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.zoom_out_btn)
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_in_btn)
        toolbar.addWidget(self.zoom_fit_btn)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.export_btn)
        root.addLayout(toolbar)

        # --- Preview section ---
        # Custom header: section label on the left, pop-out icon on the
        # right. The container itself carries the accent bar + bg so the
        # row renders as one cohesive strip.
        preview_header = QWidget()
        preview_header.setObjectName("PreviewSectionHeader")
        pheader_layout = QHBoxLayout(preview_header)
        pheader_layout.setContentsMargins(0, 0, 8, 0)
        pheader_layout.setSpacing(0)
        self._preview_section_label = QLabel(tr("veditor.section.preview").upper())
        self._preview_section_label.setObjectName("PreviewSectionTitle")
        pheader_layout.addWidget(self._preview_section_label, stretch=1)
        pheader_layout.addWidget(self.popout_btn)
        root.addWidget(preview_header)
        preview_host = QWidget()
        preview_host.setObjectName("PreviewHost")
        preview_host.setFixedHeight(280)
        preview_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        host_layout = QVBoxLayout(preview_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_label.setText(tr("veditor.no_file"))
        self._preview_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_label.setToolTip(tr("paint.hint"))
        self._preview_label.installEventFilter(self)
        self._preview_pixmap: QPixmap | None = None
        host_layout.addWidget(self._preview_label)

        # Drawing canvas — transparent overlay above the preview, below subtitles.
        # Stays in "off" tool mode so mouse events pass through to preview_label.
        self._drawing_canvas = DrawingCanvas(
            get_time_ms=lambda: self._player.position(),
            get_strokes=lambda: self._strokes,
            parent=preview_host,
        )

        # Subtitle overlay (child of preview host, positioned at bottom)
        self._subtitle_overlay = QLabel(preview_host)
        self._subtitle_overlay.setStyleSheet(
            "QLabel { color: white; "
            "background-color: rgba(0, 0, 0, 180); "
            "padding: 6px 14px; "
            "border-radius: 4px; "
            "font-size: 18px; "
            "font-weight: 600; }"
        )
        self._subtitle_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_overlay.setWordWrap(True)
        self._subtitle_overlay.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._subtitle_overlay.hide()
        self._preview_host = preview_host

        root.addWidget(preview_host, stretch=0)

        # --- Paint hint ---
        self._paint_hint_label = QLabel(tr("paint.hint"))
        self._paint_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._paint_hint_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; padding: 4px;"
        )
        root.addWidget(self._paint_hint_label)

        # --- Play bar ---
        play_bar = QWidget()
        play_bar.setObjectName("PlayBar")
        transport = QHBoxLayout(play_bar)
        transport.setContentsMargins(14, 10, 14, 10)
        transport.setSpacing(10)
        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("PlayButton")
        self.play_btn.setFixedSize(38, 38)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self._toggle_play)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("TimeLabel")

        self.current_speed_label = QLabel(
            tr("veditor.current_speed", speed="1.0")
        )
        self.current_speed_label.setObjectName("SpeedLabel")

        # Mark In / Mark Out / Clear selection — prosumer-editor style
        # range selection tied to the playhead. Tracks can still be
        # shift+dragged directly, but the buttons + I/O shortcuts are
        # the primary path now.
        self.mark_in_btn = QPushButton(tr("veditor.btn.mark_in"))
        self.mark_in_btn.setObjectName("ToolButton")
        self.mark_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_in_btn.setToolTip(tr("veditor.mark_in.tooltip"))
        self.mark_in_btn.clicked.connect(self._mark_in_at_playhead)

        self.mark_out_btn = QPushButton(tr("veditor.btn.mark_out"))
        self.mark_out_btn.setObjectName("ToolButton")
        self.mark_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_out_btn.setToolTip(tr("veditor.mark_out.tooltip"))
        self.mark_out_btn.clicked.connect(self._mark_out_at_playhead)

        self.clear_sel_btn = QPushButton(tr("veditor.btn.clear_sel_short"))
        self.clear_sel_btn.setObjectName("ToolButton")
        self.clear_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_sel_btn.setToolTip(tr("veditor.clear_sel.tooltip"))
        self.clear_sel_btn.clicked.connect(self._clear_active_selection)

        transport.addWidget(self.play_btn)
        transport.addWidget(self.time_label)
        transport.addSpacing(12)
        transport.addWidget(self.mark_in_btn)
        transport.addWidget(self.mark_out_btn)
        transport.addWidget(self.clear_sel_btn)
        transport.addStretch(1)
        transport.addWidget(self.current_speed_label)
        root.addWidget(play_bar)

        # --- Keyboard shortcuts for selection ---
        from PySide6.QtGui import QKeySequence, QShortcut
        self._sc_mark_in = QShortcut(QKeySequence("I"), self)
        self._sc_mark_in.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_mark_in.activated.connect(self._mark_in_at_playhead)
        self._sc_mark_out = QShortcut(QKeySequence("O"), self)
        self._sc_mark_out.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_mark_out.activated.connect(self._mark_out_at_playhead)
        self._sc_clear_sel = QShortcut(QKeySequence("X"), self)
        self._sc_clear_sel.setContext(Qt.ShortcutContext.WindowShortcut)
        self._sc_clear_sel.activated.connect(self._clear_active_selection)

        # --- Timeline section ---
        root.addWidget(
            self._make_section_header(tr("veditor.section.timeline"), "timeline")
        )

        # --- Track-management bar (sits right above the track view) ---
        track_bar = QHBoxLayout()
        track_bar.setContentsMargins(0, 0, 0, 0)
        track_bar.setSpacing(6)
        track_bar.addWidget(self.add_track_btn)
        track_bar.addWidget(self.add_audio_btn)
        track_bar.addWidget(self.del_track_btn)
        track_bar.addSpacing(20)

        # --- Transitions row — visible "Fade" card ---
        track_bar.addWidget(self._build_fade_card())
        track_bar.addStretch(1)
        root.addLayout(track_bar)

        # --- Tracks container (scrollable vertically). Continuous 45deg
        # stripe background so every gap / empty area reads as "timeline". ---
        self._tracks_host = StripedHost()
        self._tracks_layout = QVBoxLayout(self._tracks_host)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(0)  # rows handle their own dividers
        self._tracks_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Shared project-time ruler at the top of the scroll viewport so it
        # scrolls horizontally with the tracks.
        self._timeline_ruler = TimelineRuler()
        self._timeline_ruler.scrub_requested.connect(self._player.set_position)
        self._tracks_layout.addWidget(self._timeline_ruler)

        self._tracks_layout.addStretch(1)

        self._tracks_scroll = QScrollArea()
        self._tracks_scroll.setWidgetResizable(True)
        self._tracks_scroll.setWidget(self._tracks_host)
        self._tracks_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._tracks_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tracks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tracks_scroll.setMinimumHeight(230)
        # Keep the scroll viewport transparent so StripedHost's pattern fills
        # the entire visible area (especially below the last track).
        self._tracks_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        # Mouse wheel over the timeline zooms its horizontal length.
        self._tracks_scroll.viewport().installEventFilter(self)
        root.addWidget(self._tracks_scroll, stretch=1)

        # --- Selection / speed buttons row (controls bar) ---
        controls_bar = QWidget()
        controls_bar.setObjectName("ControlsBar")
        sel_row = QHBoxLayout(controls_bar)
        sel_row.setContentsMargins(12, 10, 12, 10)
        sel_row.setSpacing(6)
        self.selection_label = QLabel(tr("veditor.no_selection"))
        self.selection_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;"
        )
        sel_row.addWidget(self.selection_label)
        sel_row.addStretch(1)

        self._speed_buttons: list[QPushButton] = []
        for speed in SPEED_CHOICES:
            btn = QPushButton(f"{speed:g}x")
            btn.setObjectName("ToolButton")
            btn.setFixedWidth(46)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setEnabled(False)
            btn.clicked.connect(lambda _checked, s=speed: self._apply_speed_to_selection(s))
            sel_row.addWidget(btn)
            self._speed_buttons.append(btn)

        self.clear_sel_btn = QPushButton(tr("veditor.btn.clear_selection"))
        self.clear_sel_btn.setObjectName("ToolButton")
        self.clear_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_sel_btn.setEnabled(False)
        self.clear_sel_btn.clicked.connect(self._clear_selection_active_track)
        sel_row.addWidget(self.clear_sel_btn)
        root.addWidget(controls_bar)

        # --- Subtitles section ---
        root.addWidget(
            self._make_section_header(tr("veditor.section.subtitles"), "subtitles")
        )
        self._subtitle_panel = SubtitlePanel(
            position_provider=lambda: self._player.position()
        )
        self._subtitle_panel.subtitles_changed.connect(self._on_subtitles_changed)
        root.addWidget(self._subtitle_panel)

    # ------------------- track management --------------------

    def _add_empty_track(self) -> None:
        tid = self._next_track_id
        self._next_track_id += 1
        track = VideoTrack(id=tid)
        self._tracks.append(track)
        self._insert_track_widget(track)
        if self._active_track_id is None:
            self._set_active_track(tid)

    def _add_track_with_source(self, path: Path) -> None:
        tid = self._next_track_id
        self._next_track_id += 1
        track = VideoTrack(id=tid, source_path=path)
        self._tracks.append(track)
        self._insert_track_widget(track)
        self._start_thumbnail_extraction(track)
        self._set_active_track(tid)
        self._refresh_player_tracks()

    def _insert_track_widget(self, track: VideoTrack) -> None:
        row = TrackRow(track)
        row.set_px_per_sec(self._px_per_sec)
        row.clicked.connect(self._set_active_track)
        row.position_requested.connect(self._on_track_position_requested)
        row.selection_changed.connect(self._on_track_selection_changed)
        row.context_menu.connect(self._on_track_context_menu)
        row.offset_changed.connect(self._on_track_offset_changed)
        row.fades_changed.connect(self._on_track_fades_changed)
        row.media_dropped.connect(self._on_media_dropped_on_video_row)
        self._track_rows[track.id] = row
        self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, row)
        self._update_tracks_host_width()

    # ============== audio tracks (multi-clip model) ==============

    def _next_clip_id(self) -> int:
        cid = getattr(self, "_next_audio_clip_id", 1)
        self._next_audio_clip_id = cid + 1
        return cid

    def _find_audio_track(self, track_id: int) -> AudioTrack | None:
        return next((a for a in self._audio_tracks if a.id == track_id), None)

    def _find_audio_clip(self, track_id: int, clip_id: int) -> tuple[AudioTrack | None, AudioClip | None]:
        track = self._find_audio_track(track_id)
        if track is None:
            return None, None
        return track, next((c for c in track.clips if c.id == clip_id), None)

    def _add_empty_audio_track(self) -> None:
        tid = self._next_track_id
        self._next_track_id += 1
        track = AudioTrack(id=tid)
        self._audio_tracks.append(track)
        self._insert_audio_track_widget(track)

    def _add_audio_track_with_source(self, path: Path) -> None:
        duration = probe_audio_duration_ms(path)
        if duration <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.audio.error.undecodable", path=str(path)),
            )
            return
        tid = self._next_track_id
        self._next_track_id += 1
        clip = AudioClip(
            id=self._next_clip_id(),
            source_path=path,
            duration_ms=duration,
            trim_end_ms=duration,
        )
        track = AudioTrack(id=tid, clips=[clip])
        self._audio_tracks.append(track)
        self._insert_audio_track_widget(track)
        self._audio_mixer.add_track(track)
        self._start_waveform_extraction(clip)
        self._refresh_player_tracks()

    def _populate_audio_track(self, track_id: int, path: Path) -> None:
        """Fill an empty AudioTrack (no clips) with a newly-loaded file."""
        track = self._find_audio_track(track_id)
        if track is None or track.is_loaded:
            return
        duration = probe_audio_duration_ms(path)
        if duration <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.audio.error.undecodable", path=str(path)),
            )
            return
        clip = AudioClip(
            id=self._next_clip_id(),
            source_path=path,
            duration_ms=duration,
            trim_end_ms=duration,
        )
        track.clips.append(clip)
        row = self._audio_rows.get(track_id)
        if row is not None:
            row.refresh_from_track()
        self._audio_mixer.update_track(track)
        self._start_waveform_extraction(clip)
        self._refresh_player_tracks()

    def _start_waveform_extraction(self, clip: AudioClip) -> None:
        if clip.source_path is None:
            return
        prev = self._waveform_extractors.pop(clip.id, None)
        if prev is not None:
            try:
                prev.ready.disconnect()
                prev.failed.disconnect()
            except Exception:
                pass
        ex = WaveformExtractor(clip.id, clip.source_path)
        ex.ready.connect(self._on_waveform_ready)
        ex.failed.connect(self._on_waveform_failed)
        ex.finished.connect(ex.deleteLater)
        self._waveform_extractors[clip.id] = ex
        ex.start()

    def _on_waveform_ready(self, cid: int, peaks) -> None:
        for track in self._audio_tracks:
            for clip in track.clips:
                if clip.id == cid:
                    clip.waveform = peaks
                    row = self._audio_rows.get(track.id)
                    if row is not None:
                        row.clear_waveform_error(cid)
                        row.update()
                    # Refresh any open sound editor showing this clip.
                    for editor in getattr(self, "_sound_editors", []):
                        if getattr(editor, "clip", None) is clip:
                            editor.refresh_waveform()
                    self._waveform_extractors.pop(cid, None)
                    return
        self._waveform_extractors.pop(cid, None)

    def _on_waveform_failed(self, cid: int, reason: str) -> None:
        for track in self._audio_tracks:
            for clip in track.clips:
                if clip.id == cid:
                    row = self._audio_rows.get(track.id)
                    if row is not None:
                        row.set_waveform_error(cid, reason)
                    break
        self._waveform_extractors.pop(cid, None)

    def _populate_video_track(self, track_id: int, path: Path) -> None:
        track = self._find_track(track_id)
        if track is None or track.source_path is not None:
            return
        track.source_path = path
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._start_thumbnail_extraction(track)
        self._refresh_player_tracks()

    def _insert_audio_track_widget(self, track: AudioTrack) -> None:
        row = AudioTrackRow(track)
        row.set_px_per_sec(self._px_per_sec)
        row.clicked.connect(self._set_active_track)
        row.volume_changed.connect(self._on_audio_volume_changed)
        row.row_context_menu.connect(self._on_audio_row_context_menu)
        row.clip_context_menu.connect(self._on_audio_clip_context_menu)
        row.load_source_requested.connect(self._on_audio_load_source_requested)
        row.media_dropped.connect(self._on_media_dropped_on_audio_row)
        row.track_changed.connect(self._on_audio_track_changed)
        row.clip_selection_changed.connect(self._on_audio_clip_selection_changed)
        row.open_editor_requested.connect(self._open_sound_editor)
        self._audio_rows[track.id] = row
        self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, row)
        self._update_tracks_host_width()

    def _on_audio_track_changed(self, tid: int) -> None:
        """Fires whenever a clip is dragged / resized / fades mutated.
        Re-sync the mixer and refresh project duration."""
        track = self._find_audio_track(tid)
        if track is not None:
            self._audio_mixer.update_track(track)
        self._refresh_player_tracks()

    def _on_audio_clip_selection_changed(
        self, _tid: int, _cid: int, _start: int, _end: int
    ) -> None:
        # Row persists the selection on the clip; nothing else needed.
        pass

    def _split_audio_clip(self, track: AudioTrack, clip: AudioClip) -> None:
        """Split ``clip`` into two clips on the SAME track at the clip's
        current selection [sel_start, sel_end] (clip-local ms). Leaves
        the track intact with two clips that can be moved independently."""
        sel_start = clip.selection_start_ms
        sel_end = clip.selection_end_ms
        if sel_start < 0 or sel_end <= sel_start:
            return

        a_trim_start = clip.trim_start_ms
        a_trim_end = clip.trim_start_ms + sel_start
        b_trim_start = clip.trim_start_ms + sel_end
        b_trim_end = clip.effective_trim_end_ms

        a_keeps = a_trim_end > a_trim_start
        b_keeps = b_trim_end > b_trim_start
        if not a_keeps and not b_keeps:
            # Entire clip cut out — drop it from the track.
            try:
                track.clips.remove(clip)
            except ValueError:
                pass
            self._waveform_extractors.pop(clip.id, None)
            self._audio_mixer.update_track(track)
            self._refresh_player_tracks()
            self._audio_rows[track.id].update()
            return

        new_clip_b: AudioClip | None = None
        if b_keeps:
            new_clip_b = AudioClip(
                id=self._next_clip_id(),
                source_path=clip.source_path,
                duration_ms=clip.duration_ms,
                # Leave Piece B at the project-timeline position where
                # its source content used to play — there's now a real
                # gap where the cut was. User can drag either piece to
                # close the gap or move them freely.
                offset_ms=clip.offset_ms + sel_end,
                trim_start_ms=b_trim_start,
                trim_end_ms=b_trim_end,
                fade_in_ms=0,
                fade_out_ms=clip.fade_out_ms,
            )
            new_clip_b.waveform = clip.waveform  # shared source
            new_clip_b.fades = [
                FadeSegment(f.start_ms, f.end_ms, getattr(f, "kind", "both"))
                for f in clip.fades
                if f.start_ms >= b_trim_start
            ]
            new_clip_b.cuts = [
                CutSegment(
                    max(0, c.start_ms - sel_end),
                    max(0, c.end_ms - sel_end),
                )
                for c in clip.cuts
                if c.start_ms >= sel_end
            ]

        if a_keeps:
            clip.trim_end_ms = a_trim_end
            clip.fade_out_ms = 0  # tail fade belongs to piece B now
            clip.fades = [
                f for f in clip.fades if f.end_ms <= a_trim_end
            ]
            clip.cuts = [
                c for c in clip.cuts if c.end_ms <= sel_start
            ]
            clip.selection_start_ms = -1
            clip.selection_end_ms = -1
        else:
            # Piece A collapsed — remove it from the track.
            try:
                track.clips.remove(clip)
            except ValueError:
                pass

        if new_clip_b is not None:
            track.clips.append(new_clip_b)
            # Keep clips sorted by offset so the render order is stable.
            track.clips.sort(key=lambda c: c.offset_ms)

        row = self._audio_rows.get(track.id)
        if row is not None:
            row.refresh_from_track()
        self._audio_mixer.update_track(track)
        self._refresh_player_tracks()

    # ============== selection via Mark In / Mark Out (keyboard I/O) ==============

    def _mark_in_at_playhead(self) -> None:
        """Set the active track's selection start to where the playhead
        intersects that track. Works for both video and audio tracks."""
        self._set_selection_end_at_playhead(in_point=True)

    def _mark_out_at_playhead(self) -> None:
        self._set_selection_end_at_playhead(in_point=False)

    def _set_selection_end_at_playhead(self, in_point: bool) -> None:
        project_ms = self._player.position()
        candidates = self._candidate_tracks_at(project_ms)
        if not candidates:
            return
        changed = False
        for entry in candidates:
            kind = entry[0]
            if kind == "audio":
                _, track, clip = entry
                local = max(0, project_ms - clip.offset_ms)
                local = min(local, max(0, clip.effective_length_ms))
                if in_point:
                    clip.selection_start_ms = local
                    if clip.selection_end_ms < local:
                        clip.selection_end_ms = local
                else:
                    clip.selection_end_ms = local
                    if (
                        clip.selection_start_ms < 0
                        or clip.selection_start_ms > local
                    ):
                        clip.selection_start_ms = local
                row = self._audio_rows.get(track.id)
                if row is not None:
                    row.update()
            else:
                _, track = entry
                local = max(0, project_ms - getattr(track, "offset_ms", 0))
                local = min(local, max(0, track.duration_ms))
                if in_point:
                    track.selection_start_ms = local
                    if track.selection_end_ms < local:
                        track.selection_end_ms = local
                else:
                    track.selection_end_ms = local
                    if (
                        track.selection_start_ms < 0
                        or track.selection_start_ms > local
                    ):
                        track.selection_start_ms = local
                row = self._track_rows.get(track.id)
                if row is not None:
                    row.update()
            changed = True
        if changed:
            self._refresh_selection_row()

    def _clear_active_selection(self) -> None:
        for t in self._tracks:
            t.selection_start_ms = -1
            t.selection_end_ms = -1
        for track in self._audio_tracks:
            for clip in track.clips:
                clip.selection_start_ms = -1
                clip.selection_end_ms = -1
        for row in self._track_rows.values():
            row.update()
        for row in self._audio_rows.values():
            row.update()
        self._refresh_selection_row()

    def _candidate_tracks_at(self, project_ms: int) -> list:
        """Return list of entries whose window contains ``project_ms``.
        Each entry is either ("video", VideoTrack) or ("audio", track, clip)."""
        out: list = []
        active = self._active_track()
        if active is not None and active.source_path is not None:
            offset = getattr(active, "offset_ms", 0)
            if offset <= project_ms <= offset + active.duration_ms:
                out.append(("video", active))
        for t in self._tracks:
            if t is active or t.source_path is None:
                continue
            offset = getattr(t, "offset_ms", 0)
            if offset <= project_ms <= offset + t.duration_ms:
                out.append(("video", t))
        for track in self._audio_tracks:
            for clip in track.clips:
                if clip.source_path is None:
                    continue
                end = clip.offset_ms + clip.effective_length_ms
                if clip.offset_ms <= project_ms <= end:
                    out.append(("audio", track, clip))
        return out

    def _open_sound_editor(self, tid: int, cid: int) -> None:
        track, clip = self._find_audio_clip(tid, cid)
        if clip is None or clip.source_path is None:
            return
        editor = SoundEditorWindow(clip, self)
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if not hasattr(self, "_sound_editors"):
            self._sound_editors: list[SoundEditorWindow] = []
        self._sound_editors.append(editor)
        editor.destroyed.connect(
            lambda _obj, e=editor: (
                self._sound_editors.remove(e) if e in self._sound_editors else None
            )
        )
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _on_media_dropped_on_video_row(self, track_id: int, path: Path) -> None:
        if is_audio_path(path):
            self._add_audio_track_with_source(path)
            return
        if is_video_path(path):
            track = self._find_track(track_id)
            if track is not None and track.source_path is None:
                self._populate_video_track(track_id, path)
            else:
                self._add_track_with_source(path)

    def _on_media_dropped_on_audio_row(self, track_id: int, path: Path) -> None:
        """Media dropped on an audio row. Audio file → append as a new
        clip on the same track if loaded, else populate it. Video →
        spawn a new video track."""
        if is_video_path(path):
            self._add_track_with_source(path)
            return
        if not is_audio_path(path):
            return
        track = self._find_audio_track(track_id)
        if track is None:
            self._add_audio_track_with_source(path)
            return
        if not track.is_loaded:
            self._populate_audio_track(track_id, path)
            return
        # Loaded track already — append as a new clip at the tail.
        duration = probe_audio_duration_ms(path)
        if duration <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.audio.error.undecodable", path=str(path)),
            )
            return
        tail = track.extent_ms()
        clip = AudioClip(
            id=self._next_clip_id(),
            source_path=path,
            duration_ms=duration,
            offset_ms=tail,
            trim_end_ms=duration,
        )
        track.clips.append(clip)
        row = self._audio_rows.get(track_id)
        if row is not None:
            row.refresh_from_track()
        self._audio_mixer.update_track(track)
        self._start_waveform_extraction(clip)
        self._refresh_player_tracks()

    def _on_audio_volume_changed(self, tid: int, _vol: float) -> None:
        track = self._find_audio_track(tid)
        if track is not None:
            self._audio_mixer.update_track(track)

    def _on_audio_load_source_requested(self, tid: int) -> None:
        from PySide6.QtWidgets import QFileDialog
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            tr("veditor.audio.open_dialog_title"),
            "",
            tr("veditor.audio.open_filter"),
        )
        if not path_str:
            return
        self._populate_audio_track(tid, Path(path_str))

    def _on_audio_row_context_menu(self, tid: int, global_pos: QPoint) -> None:
        """Right-click on empty row area — offer row-level actions only."""
        track = self._find_audio_track(tid)
        if track is None:
            return
        menu = QMenu(self)
        act_remove = menu.addAction(tr("veditor.audio.ctx.remove"))
        chosen = menu.exec(global_pos)
        if chosen is act_remove:
            self._delete_audio_track(tid)

    def _on_audio_clip_context_menu(
        self, tid: int, cid: int, global_pos: QPoint
    ) -> None:
        """Right-click on a specific clip — per-clip actions."""
        track, clip = self._find_audio_clip(tid, cid)
        if clip is None:
            return
        menu = QMenu(self)
        act_cut_sel = QAction(tr("veditor.menu.cut_selection"), self)
        act_clear_cuts = QAction(tr("veditor.menu.clear_cuts"), self)
        act_trim = QAction(tr("veditor.audio.ctx.trim"), self)
        act_delete_clip = QAction(tr("veditor.audio.ctx.delete_clip"), self)

        def _cut_selection():
            if (
                clip.selection_start_ms < 0
                or clip.selection_end_ms <= clip.selection_start_ms
            ):
                return
            self._split_audio_clip(track, clip)

        def _clear_cuts():
            clip.cuts.clear()
            self._audio_rows[tid].update()
            self._audio_mixer.update_track(track)
            self._refresh_player_tracks()

        def _prompt_trim():
            start, ok = QInputDialog.getInt(
                self,
                tr("veditor.audio.ctx.trim"),
                tr("veditor.audio.trim_start_prompt"),
                clip.trim_start_ms, 0, max(1, clip.duration_ms), 100,
            )
            if not ok:
                return
            end, ok2 = QInputDialog.getInt(
                self,
                tr("veditor.audio.ctx.trim"),
                tr("veditor.audio.trim_end_prompt"),
                clip.effective_trim_end_ms, start + 1,
                max(start + 1, clip.duration_ms), 100,
            )
            if not ok2:
                return
            clip.trim_start_ms = int(start)
            clip.trim_end_ms = int(end)
            self._audio_rows[tid].update()
            self._audio_mixer.update_track(track)
            self._refresh_player_tracks()

        def _delete_clip():
            try:
                track.clips.remove(clip)
            except ValueError:
                return
            self._waveform_extractors.pop(clip.id, None)
            row = self._audio_rows.get(tid)
            if row is not None:
                row.refresh_from_track()
            self._audio_mixer.update_track(track)
            self._refresh_player_tracks()

        act_cut_sel.triggered.connect(_cut_selection)
        act_clear_cuts.triggered.connect(_clear_cuts)
        act_trim.triggered.connect(_prompt_trim)
        act_delete_clip.triggered.connect(_delete_clip)

        has_sel = (
            clip.selection_start_ms >= 0
            and clip.selection_end_ms > clip.selection_start_ms
        )
        act_cut_sel.setEnabled(has_sel)
        act_clear_cuts.setEnabled(bool(clip.cuts))
        menu.addAction(act_cut_sel)
        menu.addAction(act_clear_cuts)
        menu.addSeparator()
        menu.addAction(act_trim)
        menu.addSeparator()
        menu.addAction(act_delete_clip)
        menu.exec(global_pos)

    def _delete_audio_track(self, track_id: int) -> None:
        row = self._audio_rows.pop(track_id, None)
        if row is not None:
            self._tracks_layout.removeWidget(row)
            row.deleteLater()
        track = self._find_audio_track(track_id)
        if track is not None:
            for clip in track.clips:
                self._waveform_extractors.pop(clip.id, None)
        self._audio_tracks = [a for a in self._audio_tracks if a.id != track_id]
        self._audio_mixer.remove_track(track_id)
        self._refresh_player_tracks()

    def _extract_audio_from_video(self, track: VideoTrack) -> None:
        """Create a new AudioTrack whose single clip points at the video
        file itself. FFmpeg / QMediaPlayer both treat a video file as a
        valid audio source — they decode the audio stream and ignore
        the video stream — so this is effectively "ripping the BGM" as
        an editable clip on the audio lane."""
        if track.source_path is None:
            return
        duration = probe_audio_duration_ms(track.source_path)
        if duration <= 0:
            QMessageBox.warning(
                self,
                tr("veditor.title"),
                tr("veditor.menu.extract_audio_none"),
            )
            return
        tid = self._next_track_id
        self._next_track_id += 1
        clip = AudioClip(
            id=self._next_clip_id(),
            source_path=track.source_path,
            duration_ms=duration,
            # Align to the video's position on the project timeline so
            # the extracted audio stays in sync if the user never moves
            # either track afterwards.
            offset_ms=getattr(track, "offset_ms", 0),
            trim_end_ms=duration,
        )
        new_track = AudioTrack(id=tid, clips=[clip])
        self._audio_tracks.append(new_track)
        self._insert_audio_track_widget(new_track)
        self._audio_mixer.add_track(new_track)
        self._start_waveform_extraction(clip)
        self._refresh_player_tracks()

    # ============== drag & drop (window-level) ==============

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        md = event.mimeData()
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_video_path(p) or is_audio_path(p):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        if not md.hasUrls():
            event.ignore()
            return
        for u in md.urls():
            p = Path(u.toLocalFile())
            if is_video_path(p):
                self._add_track_with_source(p)
                event.acceptProposedAction()
                return
            if is_audio_path(p):
                self._add_audio_track_with_source(p)
                event.acceptProposedAction()
                return
        event.ignore()

    def _update_tracks_host_width(self) -> None:
        # Start with baseline (ruler) and each track's own preferred width.
        max_w = max(MIN_TRACK_WIDTH, self._timeline_ruler.desired_width())
        # Consider each row's natural duration-driven width.
        for row in self._track_rows.values():
            row_pref = max(MIN_TRACK_WIDTH, row._preferred_width())
            max_w = max(max_w, row_pref)
        for row in self._audio_rows.values():
            row_pref = max(MIN_TRACK_WIDTH, row._preferred_width())
            max_w = max(max_w, row_pref)
        # Also honor the viewport width so the divider / stripes can extend
        # the full visible area even when clips are short.
        vp_w = self._tracks_scroll.viewport().width() if hasattr(self, "_tracks_scroll") else 0
        max_w = max(max_w, vp_w)
        # Stretch every row + the ruler to the same width so the bottom
        # separator runs edge-to-edge regardless of clip length.
        self._timeline_ruler.setFixedWidth(max_w)
        for row in self._track_rows.values():
            row.setFixedWidth(max_w)
        for row in self._audio_rows.values():
            row.setFixedWidth(max_w)
        self._tracks_host.setMinimumWidth(max_w)

    def _change_zoom(self, factor: float) -> None:
        new_px = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, self._px_per_sec * factor))
        if abs(new_px - self._px_per_sec) < 0.001:
            return
        self._px_per_sec = new_px
        for row in self._track_rows.values():
            row.set_px_per_sec(new_px)
        for row in self._audio_rows.values():
            row.set_px_per_sec(new_px)
        self._timeline_ruler.set_px_per_sec(new_px)
        self.zoom_label.setText(self._format_zoom())
        self._update_tracks_host_width()

    def _zoom_fit(self) -> None:
        if not self._tracks:
            return
        max_span = max(
            (t.offset_ms + t.duration_ms for t in self._tracks), default=0
        )
        if max_span <= 0:
            return
        viewport_w = self._tracks_scroll.viewport().width()
        if viewport_w <= 50:
            return
        target_px = (viewport_w - 40) / (max_span / 1000.0)
        target_px = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, target_px))
        self._px_per_sec = target_px
        for row in self._track_rows.values():
            row.set_px_per_sec(target_px)
        self._timeline_ruler.set_px_per_sec(target_px)
        self.zoom_label.setText(self._format_zoom())
        self._update_tracks_host_width()

    def _format_zoom(self) -> str:
        return f"{self._px_per_sec:.0f} px/s"

    def _delete_active_track(self) -> None:
        # Allow deleting the only video track when audio tracks exist —
        # the project is still non-empty. If nothing remains at all,
        # the editor just shows the empty-timeline hint.
        if self._active_track_id is None:
            return
        if len(self._tracks) <= 1 and not self._audio_tracks:
            return
        self._delete_track(self._active_track_id)

    def _delete_track(self, track_id: int) -> None:
        row = self._track_rows.pop(track_id, None)
        if row is not None:
            self._tracks_layout.removeWidget(row)
            row.deleteLater()
        self._tracks = [t for t in self._tracks if t.id != track_id]
        ex = self._extractors.pop(track_id, None)
        if ex is not None:
            ex.stop()
        if self._active_track_id == track_id:
            self._active_track_id = None
            if self._tracks:
                self._set_active_track(self._tracks[-1].id)
        self._refresh_player_tracks()

    def _set_active_track(self, track_id: int) -> None:
        """Active track is the UI focus target for edits (speed/cut apply to
        this track). Playback cascades through ALL tracks — last-added is
        the top layer. Switching active track does NOT change what is
        playing."""
        if self._active_track_id == track_id:
            return
        self._active_track_id = track_id
        for tid, row in self._track_rows.items():
            row.set_active(tid == track_id)
        self._refresh_selection_row()

    def _refresh_player_tracks(self) -> None:
        # Include audio tracks in the project duration so playback (and
        # the timeline ruler) extend to whichever is longer — the last
        # video frame or the last audio sample.
        extra = max(
            (track.extent_ms() for track in self._audio_tracks),
            default=0,
        )
        self._player.refresh_tracks(self._tracks, extra_duration_ms=extra)
        self._update_preview_placeholder()

    def _update_preview_placeholder(self) -> None:
        """Flip the preview between "video frame", "sound-only" hint, and
        "no file" hint based on what's loaded. Called after any track
        list mutation so the preview reflects current project state.

        Avoids ``QLabel.clear()`` — that tears down both text and pixmap
        which in turn triggers a layout/resize cascade; on some timings
        that cascade re-enters ``_scale_preview_to_fit`` or the drawing
        canvas and can confuse Qt's widget lifecycle. Explicit
        ``setPixmap(QPixmap())`` + ``setText`` is surgical and leaves
        the widget's size policy alone.
        """
        has_video = any(t.source_path is not None for t in self._tracks)
        has_audio = any(t.is_loaded for t in self._audio_tracks)
        if has_video:
            return
        self._preview_pixmap = None
        self._preview_label.setPixmap(QPixmap())
        if has_audio:
            self._preview_label.setText(tr("veditor.preview.sound_only"))
            self._preview_label.setStyleSheet(
                f"color: {COLOR_ACCENT_BLUE}; font-size: 28px; font-weight: 700;"
            )
        else:
            self._preview_label.setText(tr("veditor.no_file"))
            self._preview_label.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY};"
            )

    def _find_track(self, track_id: int) -> VideoTrack | None:
        for t in self._tracks:
            if t.id == track_id:
                return t
        return None

    def _active_track(self) -> VideoTrack | None:
        if self._active_track_id is None:
            return None
        return self._find_track(self._active_track_id)

    # ----------------- thumbnails -------------------

    def _start_thumbnail_extraction(self, track: VideoTrack) -> None:
        if track.source_path is None:
            return
        prev = self._extractors.pop(track.id, None)
        if prev is not None:
            prev.stop()
        ex = ThumbnailExtractor(track.id, track.source_path, THUMB_H)
        ex.count_determined.connect(self._on_thumb_count)
        ex.thumb_ready.connect(self._on_thumb_ready)
        ex.finished_extracting.connect(self._on_extractor_done)
        track.thumbnails = []
        self._extractors[track.id] = ex
        ex.start()

    def _on_thumb_count(self, track_id: int, count: int) -> None:
        track = self._find_track(track_id)
        if track is None:
            return
        track.thumbnails = [None] * count  # type: ignore[list-item]
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()

    def _on_thumb_ready(self, track_id: int, idx: int, pix: QPixmap) -> None:
        track = self._find_track(track_id)
        if track is None:
            return
        if idx < 0 or idx >= len(track.thumbnails):
            return
        track.thumbnails[idx] = pix
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()

    def _on_extractor_done(self, track_id: int) -> None:
        ex = self._extractors.pop(track_id, None)
        if ex is not None:
            ex.deleteLater()

    # ----------------- track events -----------------

    def _on_track_position_requested(self, track_id: int, ms: int) -> None:
        # Clicking any track seeks the project (not just its own time)
        if track_id != self._active_track_id:
            self._set_active_track(track_id)
        self._player.set_position(ms)

    def _on_track_selection_changed(self, track_id: int, start: int, end: int) -> None:
        if track_id != self._active_track_id:
            self._set_active_track(track_id)
        self._refresh_selection_row()

    def _on_track_offset_changed(self, track_id: int, _new_offset_ms: int) -> None:
        # Offset repositions the clip on the project timeline → re-broadcast
        # duration and make sure the player's cached track list matches.
        self._refresh_player_tracks()
        self._update_tracks_host_width()

    def _on_track_fades_changed(self, _track_id: int) -> None:
        # Nothing to do beyond repaint (done by the row itself) — export path
        # reads the updated list at save time.
        pass

    def _on_track_context_menu(self, track_id: int, global_pos: QPoint) -> None:
        self._set_active_track(track_id)
        track = self._find_track(track_id)
        if track is None:
            return

        menu = QMenu(self)
        act_load = menu.addAction(tr("veditor.menu.load"))
        menu.addSeparator()

        has_selection = (
            track.selection_start_ms >= 0
            and track.selection_end_ms > track.selection_start_ms
        )
        act_cut = menu.addAction(tr("veditor.menu.cut_selection"))
        act_cut.setEnabled(has_selection)

        speed_menu = menu.addMenu(tr("veditor.menu.speed_selection"))
        speed_menu.setEnabled(has_selection)
        speed_actions: dict[QAction, float] = {}
        for s in SPEED_CHOICES:
            a = speed_menu.addAction(f"{s:g}x")
            speed_actions[a] = s

        act_clear_sel = menu.addAction(tr("veditor.btn.clear_selection"))
        act_clear_sel.setEnabled(has_selection)

        menu.addSeparator()
        act_extract_audio = menu.addAction(tr("veditor.menu.extract_audio"))
        act_extract_audio.setEnabled(track.source_path is not None)

        menu.addSeparator()
        act_delete = menu.addAction(tr("veditor.menu.delete_track"))
        # Can delete when another video track remains, or when audio
        # tracks exist (project won't be empty after deletion).
        act_delete.setEnabled(len(self._tracks) > 1 or bool(self._audio_tracks))

        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if chosen is act_load:
            self._load_into_track(track_id)
        elif chosen is act_cut:
            self._cut_selection_in_track(track_id)
        elif chosen in speed_actions:
            self._apply_speed_to_selection(speed_actions[chosen])
        elif chosen is act_extract_audio:
            self._extract_audio_from_video(track)
        elif chosen is act_clear_sel:
            self._clear_selection_active_track()
        elif chosen is act_delete:
            self._delete_track(track_id)

    # ------------- track actions (invoked from menu/buttons) -------------

    def _load_into_track(self, track_id: int) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("veditor.dialog.open"),
            "",
            tr("veditor.dialog.filter"),
        )
        if not path:
            return
        track = self._find_track(track_id)
        if track is None:
            return
        track.source_path = Path(path)
        track.duration_ms = 0
        track.speed_segments.clear()
        track.cuts.clear()
        track.thumbnails = []
        track.selection_start_ms = -1
        track.selection_end_ms = -1
        # Force the player to re-open this track's capture so it picks up the
        # new source (refresh_tracks only reopens on cap-missing currently)
        self._player._release_cap(track.id)
        self._refresh_player_tracks()
        self._start_thumbnail_extraction(track)
        row = self._track_rows.get(track_id)
        if row is not None:
            row._recalc_width()
            row.update()
        self._refresh_selection_row()

    def _cut_selection_in_track(self, track_id: int) -> None:
        track = self._find_track(track_id)
        if track is None:
            return
        s, e = track.selection_start_ms, track.selection_end_ms
        if s < 0 or e <= s:
            return
        merged: list[CutSegment] = []
        new_start, new_end = s, e
        for c in track.cuts:
            overlaps = not (c.end_ms <= new_start or new_end <= c.start_ms)
            if overlaps:
                new_start = min(new_start, c.start_ms)
                new_end = max(new_end, c.end_ms)
            else:
                merged.append(c)
        # Remove overlapping speed segments too
        track.speed_segments = [
            seg
            for seg in track.speed_segments
            if not seg.overlaps(new_start, new_end)
        ]
        merged.append(CutSegment(new_start, new_end))
        merged.sort(key=lambda c: c.start_ms)
        track.cuts = merged
        track.selection_start_ms = -1
        track.selection_end_ms = -1
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._refresh_selection_row()

    def _apply_speed_to_selection(self, speed: float) -> None:
        track = self._active_track()
        if track is None:
            return
        s, e = track.selection_start_ms, track.selection_end_ms
        if s < 0 or e <= s:
            return

        kept = [seg for seg in track.speed_segments if not seg.overlaps(s, e)]
        # Split existing segments that straddle the boundaries
        for seg in track.speed_segments:
            if seg.overlaps(s, e):
                if seg.start_ms < s:
                    kept.append(SpeedSegment(seg.start_ms, s, seg.speed))
                if seg.end_ms > e:
                    kept.append(SpeedSegment(e, seg.end_ms, seg.speed))
        kept.append(SpeedSegment(s, e, speed))
        kept.sort(key=lambda seg: seg.start_ms)
        track.speed_segments = kept

        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()

        if track.id == self._active_track_id:
            pos = self._player.position()
            if s <= pos < e:
                self._current_segment_speed = speed
                self._player.set_speed(speed)
                self.current_speed_label.setText(
                    tr("veditor.current_speed", speed=f"{speed:g}")
                )

    def _clear_selection_active_track(self) -> None:
        track = self._active_track()
        if track is None:
            return
        track.selection_start_ms = -1
        track.selection_end_ms = -1
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        self._refresh_selection_row()

    def _on_reset_active_track(self) -> None:
        track = self._active_track()
        if track is None:
            return
        track.speed_segments.clear()
        track.cuts.clear()
        track.selection_start_ms = -1
        track.selection_end_ms = -1
        self._player.set_speed(1.0)
        self._current_segment_speed = 1.0
        self.current_speed_label.setText(
            tr("veditor.current_speed", speed="1.0")
        )
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        self._refresh_selection_row()

    # -------------- player integration --------------

    def _toggle_play(self) -> None:
        self._player.toggle()

    def _on_playback_state_changed(self, state) -> None:
        self.play_btn.setText("⏸" if state is PlayerState.PLAYING else "▶")

    def _on_frame_ready(self, qimg: QImage) -> None:
        # In audio-only projects the player still ticks (so AudioMixer
        # stays synced) and emits blank frames. Don't clobber the
        # "🎵 Sound only" placeholder in that case.
        has_video = any(t.source_path is not None for t in self._tracks)
        if not has_video:
            return
        # Keep the clean original in _preview_pixmap so PaintDialog sees the
        # real frame; fade is applied only to the displayed scaled copy
        # inside _scale_preview_to_fit.
        self._preview_pixmap = QPixmap.fromImage(qimg)
        self._scale_preview_to_fit()
        self._update_subtitle_overlay(self._player.position())
        # The overlay is a child — bring on top of preview label each frame
        self._drawing_canvas.raise_()
        self._subtitle_overlay.raise_()
        self._drawing_canvas.update()
        # Mirror the frame to the pop-out window when one is open.
        if self._preview_popout is not None:
            try:
                self._preview_popout.update_frame(qimg)
            except Exception:
                pass

    def _toggle_preview_popout(self) -> None:
        """Open a separate top-level preview window (for multi-monitor
        full-screen viewing), or close it and return focus here."""
        if self._preview_popout is not None:
            self._preview_popout.close()
            return
        popout = PreviewPopoutWindow()
        popout.closed.connect(self._on_preview_popout_closed)
        popout.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        # Seed the popout with the latest frame if one is cached, so
        # users don't see a black box until the next tick.
        if self._preview_pixmap is not None and not self._preview_pixmap.isNull():
            popout.update_frame(self._preview_pixmap.toImage())
        popout.show()
        self._preview_popout = popout
        self.popout_btn.setProperty("popped", True)
        self.popout_btn.setToolTip(tr("veditor.popout.tooltip_docked"))
        self.popout_btn.style().unpolish(self.popout_btn)
        self.popout_btn.style().polish(self.popout_btn)

    def _on_preview_popout_closed(self) -> None:
        self._preview_popout = None
        self.popout_btn.setProperty("popped", False)
        self.popout_btn.setToolTip(tr("veditor.popout.tooltip"))
        self.popout_btn.style().unpolish(self.popout_btn)
        self.popout_btn.style().polish(self.popout_btn)

    def _current_fade_multiplier(self, pos_ms: int) -> float:
        """1.0 = full brightness, 0.0 = black. Picks whichever fade on the
        active track contains ``pos_ms`` (project time) and computes its
        in/out multiplier based on kind."""
        track = self._active_track()
        if track is None or not track.fades:
            return 1.0
        local = pos_ms - getattr(track, "offset_ms", 0)
        for fade in track.fades:
            if not fade.contains(local):
                continue
            span = fade.duration_ms
            if span <= 0:
                return 1.0
            t = (local - fade.start_ms) / span  # 0..1 within the fade
            kind = getattr(fade, "kind", "both")
            if kind == "in":
                return t
            if kind == "out":
                return 1.0 - t
            # both: content→black→content
            return 1.0 - 2.0 * abs(t - 0.5)
        return 1.0

    def _update_subtitle_overlay(self, pos_ms: int) -> None:
        sub = self._subtitle_panel.active_subtitle(pos_ms)
        if sub is None or not sub.text.strip():
            self._subtitle_overlay.hide()
            return
        self._subtitle_overlay.setText(sub.text)
        if sub.show_box:
            self._subtitle_overlay.setStyleSheet(
                "QLabel { color: white; "
                "background-color: rgba(0, 0, 0, 180); "
                "padding: 6px 14px; border-radius: 4px; "
                "font-size: 18px; font-weight: 600; }"
            )
        else:
            # No background box — use a text-shadow-like effect via font weight.
            # Qt QLabel has no native text-shadow, but heavier font + white on
            # most content is legible; the export step adds a real outline.
            self._subtitle_overlay.setStyleSheet(
                "QLabel { color: white; "
                "background-color: transparent; "
                "padding: 4px 10px; "
                "font-size: 20px; font-weight: 900; }"
            )
        self._reposition_subtitle_overlay()
        self._subtitle_overlay.show()

    def _reposition_subtitle_overlay(self) -> None:
        host = self._preview_host
        host_size = host.size()
        self._subtitle_overlay.adjustSize()
        ov_w = min(int(host_size.width() * 0.9), max(200, self._subtitle_overlay.width()))
        ov_h = self._subtitle_overlay.heightForWidth(ov_w)
        if ov_h <= 0:
            ov_h = self._subtitle_overlay.height()
        x = (host_size.width() - ov_w) // 2
        y = host_size.height() - ov_h - 12
        self._subtitle_overlay.setFixedWidth(ov_w)
        self._subtitle_overlay.move(max(0, x), max(0, y))

    def _on_subtitles_changed(self) -> None:
        self._update_subtitle_overlay(self._player.position())

    # ---------- drawing ----------

    def eventFilter(self, obj, event):
        if obj is getattr(self, "_preview_label", None):
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._open_paint_dialog()
                    return True
                if event.button() == Qt.MouseButton.RightButton:
                    self._show_preview_context_menu(event.globalPosition().toPoint())
                    return True
        # Wheel over the tracks area zooms the timeline (clip length).
        # Guard: eventFilter may fire during UI build before the scroll area
        # has been constructed.
        scroll = getattr(self, "_tracks_scroll", None)
        if (
            scroll is not None
            and obj is scroll.viewport()
            and event.type() == event.Type.Wheel
        ):
            delta = event.angleDelta().y()
            if delta > 0:
                self._change_zoom(1.2)
            elif delta < 0:
                self._change_zoom(1 / 1.2)
            return True
        return super().eventFilter(obj, event)

    def _show_preview_context_menu(self, global_pos) -> None:
        menu = QMenu(self)
        clear_action = menu.addAction(tr("paint.btn.clear_all"))
        clear_action.setEnabled(bool(self._strokes))
        chosen = menu.exec(global_pos)
        if chosen is clear_action:
            self._strokes.clear()
            self._drawing_canvas.update()

    def _open_paint_dialog(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        # Pause playback while drawing so the background stays fixed.
        was_playing = self._player.state() is PlayerState.PLAYING
        if was_playing:
            self._player.pause()

        from app.drawing import PaintDialog

        # Hide preview bubble items while editing in the dialog; respawn after.
        for item in list(self._bubble_items):
            item.deleteLater()
        self._bubble_items.clear()

        dlg = PaintDialog(
            background_pixmap=self._preview_pixmap,
            initial_strokes=self._strokes,
            time_ms=self._player.position(),
            parent=self,
            initial_bubbles=self._bubbles,
        )
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._strokes = dlg.result_strokes()
            self._bubbles = dlg.result_bubbles()
            self._drawing_canvas.update()
        # Respawn passive items so the user sees bubbles on the preview.
        for bubble in self._bubbles:
            self._spawn_bubble_item(bubble)
        self._update_bubble_visibility(self._player.position())

    # ------------- speech bubbles -------------

    def _spawn_bubble_item(self, bubble: SpeechBubble) -> SpeechBubbleItem:
        # Parent to the drawing canvas (already sized to the video rect), so
        # normalized coords map to the actual video area, not letterbox.
        item = SpeechBubbleItem(bubble, self._drawing_canvas)
        item.sync_to_parent()
        item.show()
        item.moved.connect(lambda it=item: it.sync_to_bubble())
        item.deleted.connect(lambda it=item, b=bubble: self._remove_bubble(b, it))
        self._bubble_items.append(item)
        return item

    def _remove_bubble(self, bubble: SpeechBubble, item: SpeechBubbleItem) -> None:
        try:
            self._bubbles.remove(bubble)
        except ValueError:
            pass
        try:
            self._bubble_items.remove(item)
        except ValueError:
            pass
        item.deleteLater()

    def _resync_bubbles_to_preview(self) -> None:
        for item in self._bubble_items:
            item.sync_to_parent()

    def _update_bubble_visibility(self, pos_ms: int) -> None:
        for item in self._bubble_items:
            item.setVisible(item.bubble.start_ms <= int(pos_ms))

    def _scale_preview_to_fit(self) -> None:
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            return
        avail = self._preview_label.size()
        if avail.width() <= 0 or avail.height() <= 0:
            return
        scaled = self._preview_pixmap.scaled(
            avail,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Blend to black by the active fade's multiplier so the preview
        # matches what the exporter produces.
        mult = self._current_fade_multiplier(self._player.position())
        if mult < 0.999:
            faded = QPixmap(scaled.size())
            faded.fill(Qt.GlobalColor.black)
            p = QPainter(faded)
            p.setOpacity(max(0.0, min(1.0, mult)))
            p.drawPixmap(0, 0, scaled)
            p.end()
            scaled = faded
        self._preview_label.setPixmap(scaled)
        self._sync_overlay_to_video_rect()

    def _sync_overlay_to_video_rect(self) -> None:
        """Size the drawing canvas to exactly the video pixmap rect inside the
        preview label, so strokes can't render in the letterbox area."""
        host = self._preview_host
        if self._preview_pixmap is None or self._preview_pixmap.isNull():
            self._drawing_canvas.setGeometry(0, 0, host.width(), host.height())
            return
        # preview_label is laid out inside host via a QVBoxLayout with zero
        # margins, so label top-left == host top-left in host coords.
        label_w = self._preview_label.width()
        label_h = self._preview_label.height()
        if label_w <= 0 or label_h <= 0:
            return
        src_w = self._preview_pixmap.width()
        src_h = self._preview_pixmap.height()
        if src_w <= 0 or src_h <= 0:
            return
        scale = min(label_w / src_w, label_h / src_h)
        vw = max(1, int(src_w * scale))
        vh = max(1, int(src_h * scale))
        vx = (label_w - vw) // 2
        vy = (label_h - vh) // 2
        self._drawing_canvas.setGeometry(vx, vy, vw, vh)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_preview_to_fit()
        if self._subtitle_overlay.isVisible():
            self._reposition_subtitle_overlay()
        self._sync_overlay_to_video_rect()
        self._resync_bubbles_to_preview()
        # Timeline stretches to viewport width too
        if hasattr(self, "_tracks_scroll"):
            self._update_tracks_host_width()

    def _on_position_changed(self, pos: int) -> None:
        # Playhead shows on every track at project time
        for row in self._track_rows.values():
            row.set_position(pos)
        for row in self._audio_rows.values():
            row.set_position(pos)
        self._timeline_ruler.set_playhead(pos)
        self.time_label.setText(
            f"{_format_ms(pos)} / {_format_ms(self._player.duration())}"
        )
        self._update_subtitle_overlay(pos)
        # Re-apply fade to the preview at the new playhead (player only emits
        # new frames on seek or advance; a pause during a fade needs refresh).
        self._scale_preview_to_fit()
        # Drawings can appear/disappear based on current time
        self._drawing_canvas.update()
        # Bubbles also gate on the current playhead
        self._update_bubble_visibility(pos)

        # Report speed at the currently-rendered track. Translate project time
        # into each track's local time via its offset so speed/cut ranges align.
        active_for_render = None
        for t in reversed(self._tracks):
            if t.source_path is None:
                continue
            offset = getattr(t, "offset_ms", 0)
            local = pos - offset
            if local < 0 or local >= t.duration_ms:
                continue
            if any(c.start_ms <= local < c.end_ms for c in t.cuts):
                continue
            active_for_render = t
            break
        if active_for_render is None:
            speed = 1.0
        else:
            local_pos = pos - getattr(active_for_render, "offset_ms", 0)
            speed = self._speed_at(active_for_render, local_pos)
        if speed != self._current_segment_speed:
            self._current_segment_speed = speed
            self.current_speed_label.setText(
                tr("veditor.current_speed", speed=f"{speed:g}")
            )

    def _on_duration_changed(self, dur: int) -> None:
        for row in self._track_rows.values():
            row._recalc_width()
        self._timeline_ruler.set_project_duration(dur)
        self._update_tracks_host_width()
        self.time_label.setText(f"0:00 / {_format_ms(dur)}")
        self._subtitle_panel.set_project_duration(dur)

    def _on_player_error(self, error, msg: str) -> None:
        if error == QMediaPlayer.Error.NoError:
            return
        import sys as _sys

        print(f"[veditor] player error {error}: {msg}", file=_sys.stderr, flush=True)
        QMessageBox.warning(
            self,
            tr("veditor.title"),
            f"{msg}\n\n"
            "Codec or file format may not be supported by Windows Media Foundation.",
        )

    def _on_media_status(self, status) -> None:
        import sys as _sys

        print(f"[veditor] media status: {status}", file=_sys.stderr, flush=True)

    @staticmethod
    def _speed_at(track: VideoTrack, pos_ms: int) -> float:
        for seg in track.speed_segments:
            if seg.contains(pos_ms):
                return seg.speed
        return 1.0

    # -------------- selection UI --------------

    def _refresh_selection_row(self) -> None:
        track = self._active_track()
        if track is None:
            has_sel = False
            self.selection_label.setText(tr("veditor.no_selection"))
        else:
            has_sel = (
                track.selection_start_ms >= 0
                and track.selection_end_ms > track.selection_start_ms
            )
            if has_sel:
                self.selection_label.setText(
                    tr(
                        "veditor.selection_range",
                        start=_format_ms(track.selection_start_ms),
                        end=_format_ms(track.selection_end_ms),
                        duration=_format_ms(
                            track.selection_end_ms - track.selection_start_ms
                        ),
                    )
                )
            else:
                self.selection_label.setText(tr("veditor.no_selection"))
        for btn in self._speed_buttons:
            btn.setEnabled(has_sel)
        self.clear_sel_btn.setEnabled(has_sel)

    # -------------- keyboard shortcuts --------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Space:
            self._toggle_play()
            return
        track = self._active_track()
        step = 5000 if mods & Qt.KeyboardModifier.ShiftModifier else 1000
        if key == Qt.Key.Key_Left:
            self._player.set_position(max(0, self._player.position() - step))
            return
        if key == Qt.Key.Key_Right:
            end = track.duration_ms if track else 0
            self._player.set_position(min(end, self._player.position() + step))
            return
        if key == Qt.Key.Key_Home:
            self._player.set_position(0)
            return
        if key == Qt.Key.Key_End and track:
            self._player.set_position(track.duration_ms)
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        for ex in list(self._extractors.values()):
            ex.stop()
        for ex in list(self._extractors.values()):
            ex.wait(300)
        try:
            self._player.release()
        except Exception:
            pass
        super().closeEvent(event)

    # -------- export --------

    def _on_export(self) -> None:
        track = self._active_track()
        if track is None or track.source_path is None:
            QMessageBox.warning(
                self, tr("veditor.title"), tr("veditor.export.no_source")
            )
            return
        segments = build_segments(track.duration_ms, track.cuts, track.speed_segments)
        if not segments:
            QMessageBox.warning(
                self, tr("veditor.title"), tr("veditor.export.no_segments")
            )
            return

        default_name = f"{track.source_path.stem}_edited.mp4"
        default_path = track.source_path.parent / default_name
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("veditor.export.dialog_title"),
            str(default_path),
            tr("veditor.export.filter"),
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != ".mp4":
            out = out.with_suffix(".mp4")

        from PySide6.QtWidgets import QProgressDialog

        total = int(sum((e - s) / sp for (s, e, sp) in segments) + 0.5)
        dlg = QProgressDialog(
            tr("veditor.export.note"),
            None,
            0,
            max(1, total),
            self,
        )
        dlg.setWindowTitle(tr("veditor.export.progress_title"))
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setCancelButton(None)
        dlg.show()

        thread = VideoExportThread(
            track.source_path,
            out,
            segments,
            self._subtitle_panel.subtitles(),
            self._strokes,
            cuts=track.cuts,
            fade_segments=track.fades,
            bubbles=self._bubbles,
            audio_tracks=[t for t in self._audio_tracks if t.is_loaded],
        )
        thread.progress.connect(
            lambda cur, tot: (dlg.setMaximum(max(1, tot)), dlg.setValue(cur))
        )
        thread.stage.connect(
            lambda s: dlg.setLabelText(f"{s}\n\n{tr('veditor.export.note')}")
        )

        def _on_success(p: Path, size: int) -> None:
            dlg.close()
            QMessageBox.information(
                self,
                tr("veditor.title"),
                tr(
                    "veditor.export.done",
                    path=str(p),
                    size=_format_size(size),
                ),
            )

        def _on_error(msg: str) -> None:
            dlg.close()
            QMessageBox.critical(
                self, tr("veditor.export.failed"), msg
            )

        thread.finished_success.connect(_on_success)
        thread.finished_error.connect(_on_error)
        thread.finished.connect(thread.deleteLater)
        self._export_thread = thread  # keep reference
        thread.start()

    def _on_player_error(self, msg: str) -> None:
        import sys as _sys

        print(f"[veditor] player error: {msg}", file=_sys.stderr, flush=True)
        QMessageBox.warning(self, tr("veditor.title"), msg)


def _format_ms(ms: int) -> str:
    ms = max(0, int(ms))
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"
