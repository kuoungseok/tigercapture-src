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
    QFont,
    QImage,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QDialog,
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
    QToolButton,
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
from app.typography import (
    TEXT_CLIP_MIME,
    AnimationConfig,
    TextClip,
    TextStyle,
    TextTrack,
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
SPEED_MIME_TYPE = "application/x-gifcam-speed"


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


def _new_color_grade():
    """Lazy-import ColorGrade default factory — keeps the import at
    module import time deferred so the cycle (color_grading is imported
    elsewhere) stays clean."""
    from app.color_grading import ColorGrade
    return ColorGrade()


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
    # Typography actors placed directly on this track's strip. They
    # overlay the video at their time windows; each actor carries its
    # own text, style, and (future) animation config. Times are track-
    # local source ms (the TrackRow paints them in project time via the
    # offset + speed mapping the row already knows).
    typography_actors: list = field(default_factory=list)  # list[TextClip]
    # Per-track color grading (5 sliders + preset metadata). Preview
    # applies it via numpy on each frame; export injects ``eq +
    # colorbalance`` into the ffmpeg filter graph after concat.
    color_grade: "ColorGrade" = field(default_factory=lambda: _new_color_grade())

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
    TYPO_EDGE_GRAB_PX = 8
    TYPO_CHIP_H = 22             # height of the typography chip strip
    TYPO_MIN_DURATION_MS = 200
    SPEED_EDGE_GRAB_PX = 8
    SPEED_MIN_DURATION_MS = 200

    offset_changed = Signal(int, int)  # track_id, new_offset_ms
    fades_changed = Signal(int)  # track_id — fade segments added / resized
    speed_changed = Signal(int)  # track_id — speed segments added / changed
    media_dropped = Signal(int, object)  # track_id, Path — any media file
    typography_double_clicked = Signal(int, int)    # track_id, clip_id
    typography_context_menu = Signal(int, int, object)   # track_id, clip_id, global pos
    typography_changed = Signal(int)                # track_id — add/move/resize

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
        # Typography-actor drag state
        self._typo_drag_mode: str | None = None        # "move"/"resize_l"/"resize_r"
        self._typo_drag_actor_id: int | None = None
        self._typo_drag_anchor_ms: int = 0
        self._typo_drag_orig_start_ms: int = 0
        self._typo_drag_orig_end_ms: int = 0
        # Hover tracking for edge-handle highlighting
        self._hover_fade: FadeSegment | None = None
        self._hover_fade_side: str = ""
        self._hover_typo_actor_id: int | None = None
        self._hover_typo_side: str = ""
        self._hover_speed_seg: SpeedSegment | None = None
        self._hover_speed_side: str = ""
        # Speed-segment drag state (resize only — body clicks keep the
        # existing track-offset-drag behavior so users can still slide
        # the whole track by grabbing it anywhere).
        self._speed_drag_mode: str | None = None     # "resize_l" / "resize_r"
        self._speed_drag_seg: SpeedSegment | None = None
        self._speed_drag_anchor_ms: int = 0
        self._speed_drag_orig_start: int = 0
        self._speed_drag_orig_end: int = 0

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

            # Thumbnails — fixed native aspect, centered on their time
            # position. Clip to the clip body's rect so the first/last
            # thumbnails can't spill past the video's actual start/end
            # (otherwise fade actors placed at the edges appear to have
            # a visual gap with the video content).
            if self.track.thumbnails and self.track.duration_ms > 0:
                n = len(self.track.thumbnails)
                track_h = rect.height()
                painter.save()
                painter.setClipRect(rect)
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
                painter.restore()
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
            # Edge trim handles (blue — matches the SpeedCard accent).
            is_hover = self._hover_speed_seg is seg
            is_drag = self._speed_drag_seg is seg
            self._paint_edge_handles(
                painter,
                rect_top=rect.top(),
                rect_h=rect.height(),
                x_left=x1,
                x_right=x2,
                left_hot=(is_hover and self._hover_speed_side == "left")
                    or (is_drag and self._speed_drag_mode == "resize_l"),
                right_hot=(is_hover and self._hover_speed_side == "right")
                    or (is_drag and self._speed_drag_mode == "resize_r"),
                dragging=is_drag,
                base_color=QColor(120, 180, 240, 220),
                accent_color=QColor("#4a9bee"),
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

        # Typography actors — orange→pink gradient chips at the top of the
        # track strip. Draw AFTER fades so they always read on top.
        for actor in getattr(self.track, "typography_actors", []):
            self._paint_typography_actor(painter, actor, rect)

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

        # Edge trim handles — always visible (invites resizing), widen +
        # brighten on hover, light up with accent during active drag.
        self._paint_edge_handles(
            painter,
            rect_top=rect.top(),
            rect_h=rect.height(),
            x_left=fx1,
            x_right=fx2,
            left_hot=(self._hover_fade is fade and self._hover_fade_side == "left")
                or (self._resizing_fade is fade and self._resize_side == "left"),
            right_hot=(self._hover_fade is fade and self._hover_fade_side == "right")
                or (self._resizing_fade is fade and self._resize_side == "right"),
            dragging=(self._resizing_fade is fade),
            base_color=QColor(255, 150, 80),
            accent_color=QColor("#ff7a4a"),
        )

    def _paint_edge_handles(
        self,
        painter: QPainter,
        *,
        rect_top: int,
        rect_h: int,
        x_left: int,
        x_right: int,
        left_hot: bool,
        right_hot: bool,
        dragging: bool,
        base_color: QColor,
        accent_color: QColor,
    ) -> None:
        """Draw two trim handles at the actor's edges. Each handle
        widens when hovered (6px) or being dragged (8px), and uses the
        accent color during drag."""
        def _one(x: int, hot: bool) -> None:
            if dragging and hot:
                w = 8
                color = accent_color
            elif hot:
                w = 6
                color = QColor(accent_color)
                color.setAlpha(255)
            else:
                w = 4
                color = QColor(base_color)
                color.setAlpha(210)
            painter.fillRect(x - w // 2, rect_top, w, rect_h, color)
            # Small notch marks top + bottom so the handle reads as a
            # "grabbable bar" rather than a color stripe.
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
            notch = max(2, w - 2)
            painter.drawLine(
                x - notch // 2, rect_top + 2,
                x + notch // 2, rect_top + 2,
            )
            painter.drawLine(
                x - notch // 2, rect_top + rect_h - 3,
                x + notch // 2, rect_top + rect_h - 3,
            )

        _one(x_left, left_hot)
        _one(x_right, right_hot)

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

        # Typography actor interactions take priority over everything
        # else — they sit at the top of the strip and must be movable
        # / resizable without triggering the clip body's drag-to-move.
        typo_actor, typo_zone = self._typography_at(pos)
        if typo_actor is not None:
            self._typo_drag_actor_id = typo_actor.id
            self._typo_drag_anchor_ms = self._x_to_ms(x)
            self._typo_drag_orig_start_ms = int(typo_actor.start_ms)
            self._typo_drag_orig_end_ms = int(typo_actor.end_ms)
            if typo_zone == "left":
                self._typo_drag_mode = "resize_l"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif typo_zone == "right":
                self._typo_drag_mode = "resize_r"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self._typo_drag_mode = "move"
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
            return

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

        # Speed edge resize (after fades — when a fade and a speed
        # segment share an edge pixel, fade wins; rare in practice).
        seg, s_side = self._speed_edge_at(x, pos.y())
        if seg is not None:
            self._speed_drag_seg = seg
            self._speed_drag_mode = "resize_l" if s_side == "left" else "resize_r"
            self._speed_drag_anchor_ms = self._x_to_ms(x)
            self._speed_drag_orig_start = int(seg.start_ms)
            self._speed_drag_orig_end = int(seg.end_ms)
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

        # Typography drag — active
        if self._typo_drag_mode is not None and self._typo_drag_actor_id is not None:
            actor = None
            for a in self.track.typography_actors:
                if a.id == self._typo_drag_actor_id:
                    actor = a
                    break
            if actor is None:
                self._typo_drag_mode = None
            else:
                delta_ms = self._x_to_ms(x) - self._typo_drag_anchor_ms
                if self._typo_drag_mode == "move":
                    new_start = max(0, self._typo_drag_orig_start_ms + delta_ms)
                    duration = self._typo_drag_orig_end_ms - self._typo_drag_orig_start_ms
                    if new_start + duration > self.track.duration_ms:
                        new_start = max(0, self.track.duration_ms - duration)
                    actor.start_ms = new_start
                    actor.end_ms = new_start + duration
                elif self._typo_drag_mode == "resize_l":
                    new_start = max(0, self._typo_drag_orig_start_ms + delta_ms)
                    new_start = min(
                        new_start, actor.end_ms - self.TYPO_MIN_DURATION_MS
                    )
                    actor.start_ms = new_start
                elif self._typo_drag_mode == "resize_r":
                    new_end = max(
                        actor.start_ms + self.TYPO_MIN_DURATION_MS,
                        self._typo_drag_orig_end_ms + delta_ms,
                    )
                    new_end = min(new_end, self.track.duration_ms)
                    actor.end_ms = new_end
                self.update()
                self.typography_changed.emit(self.track.id)
                return

        # Speed edge resize — active drag
        if self._speed_drag_mode is not None and self._speed_drag_seg is not None:
            seg = self._speed_drag_seg
            mouse_ms = self._x_to_ms(x)
            delta = mouse_ms - self._speed_drag_anchor_ms
            # Compute adjacent-segment bounds so we can't cross into
            # a neighbouring speed segment.
            neighbours = [s for s in self.track.speed_segments if s is not seg]
            if self._speed_drag_mode == "resize_l":
                # Max start = current end - MIN. Min start = closest
                # left neighbour's end (or 0).
                left_cap = max(
                    (s.end_ms for s in neighbours if s.end_ms <= self._speed_drag_orig_start),
                    default=0,
                )
                new_start = max(
                    left_cap,
                    min(seg.end_ms - self.SPEED_MIN_DURATION_MS,
                        self._speed_drag_orig_start + delta),
                )
                seg.start_ms = int(new_start)
            else:  # resize_r
                right_cap = min(
                    (s.start_ms for s in neighbours if s.start_ms >= self._speed_drag_orig_end),
                    default=self.track.duration_ms,
                )
                new_end = min(
                    right_cap,
                    max(seg.start_ms + self.SPEED_MIN_DURATION_MS,
                        self._speed_drag_orig_end + delta),
                )
                seg.end_ms = int(new_end)
            self.update()
            self.speed_changed.emit(self.track.id)
            return

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

        # Idle hover — swap cursor when the pointer is over a fade edge
        # or typography actor so the user discovers the affordances.
        # Also update hover-state fields so paint can thicken the edge
        # handles on the thing under the cursor.
        if not (self._dragging_offset or self._dragging_selection
                or self._dragging_playhead):
            typo_actor, typo_zone = self._typography_at(pos)

            prev_typo_id = self._hover_typo_actor_id
            prev_typo_side = self._hover_typo_side
            prev_fade = self._hover_fade
            prev_fade_side = self._hover_fade_side
            prev_speed = self._hover_speed_seg
            prev_speed_side = self._hover_speed_side

            if typo_actor is not None:
                self._hover_typo_actor_id = typo_actor.id
                self._hover_typo_side = typo_zone if typo_zone in ("left", "right") else ""
                self._hover_fade = None
                self._hover_fade_side = ""
                self._hover_speed_seg = None
                self._hover_speed_side = ""
                self.setCursor(
                    Qt.CursorShape.SizeHorCursor if typo_zone in ("left", "right")
                    else Qt.CursorShape.OpenHandCursor
                )
            else:
                self._hover_typo_actor_id = None
                self._hover_typo_side = ""
                fade, side = self._fade_edge_at(x, pos.y())
                if fade is not None:
                    self._hover_fade = fade
                    self._hover_fade_side = side
                    self._hover_speed_seg = None
                    self._hover_speed_side = ""
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                else:
                    self._hover_fade = None
                    self._hover_fade_side = ""
                    seg, s_side = self._speed_edge_at(x, pos.y())
                    if seg is not None:
                        self._hover_speed_seg = seg
                        self._hover_speed_side = s_side
                        self.setCursor(Qt.CursorShape.SizeHorCursor)
                    else:
                        self._hover_speed_seg = None
                        self._hover_speed_side = ""
                        self.setCursor(Qt.CursorShape.OpenHandCursor)

            if (
                prev_typo_id != self._hover_typo_actor_id
                or prev_typo_side != self._hover_typo_side
                or prev_fade is not self._hover_fade
                or prev_fade_side != self._hover_fade_side
                or prev_speed is not self._hover_speed_seg
                or prev_speed_side != self._hover_speed_side
            ):
                self.update()

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

    def leaveEvent(self, _event) -> None:
        # Clear hover state when the cursor exits the widget, otherwise
        # the last-hovered handle stays "hot" forever.
        if (self._hover_fade is not None
                or self._hover_typo_actor_id is not None
                or self._hover_speed_seg is not None):
            self._hover_fade = None
            self._hover_fade_side = ""
            self._hover_typo_actor_id = None
            self._hover_typo_side = ""
            self._hover_speed_seg = None
            self._hover_speed_side = ""
            self.update()

    def wheelEvent(self, event) -> None:
        """Scroll wheel over a speed segment cycles through preset
        rates — gives users a quick way to tweak the speed in place
        without opening the context menu."""
        pos = event.position().toPoint()
        seg = self._speed_segment_under(pos)
        if seg is None:
            super().wheelEvent(event)
            return
        try:
            idx = SpeedCard.PRESETS.index(
                min(SpeedCard.PRESETS, key=lambda p: abs(p - seg.speed))
            )
        except ValueError:
            idx = SpeedCard.PRESETS.index(SpeedCard.DEFAULT_SPEED)
        delta_y = event.angleDelta().y()
        step = 1 if delta_y > 0 else -1
        new_idx = max(0, min(len(SpeedCard.PRESETS) - 1, idx + step))
        seg.speed = float(SpeedCard.PRESETS[new_idx])
        self.update()
        self.speed_changed.emit(self.track.id)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._speed_drag_mode is not None:
            # Keep segments ordered for subsequent hit-tests / painting.
            self.track.speed_segments.sort(key=lambda s: s.start_ms)
            self._speed_drag_mode = None
            self._speed_drag_seg = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.speed_changed.emit(self.track.id)
            self.update()
        if self._typo_drag_mode is not None:
            # Re-sort by start_ms so paint + hit-testing stay consistent.
            self.track.typography_actors.sort(key=lambda c: c.start_ms)
            self._typo_drag_mode = None
            self._typo_drag_actor_id = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.typography_changed.emit(self.track.id)
            self.update()
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
        # Typography actors have priority — they sit visually on top
        # of the timeline strip.
        typo_actor, _zone = self._typography_at(local_pos)
        if typo_actor is not None:
            self.typography_context_menu.emit(
                self.track.id, typo_actor.id, self.mapToGlobal(local_pos)
            )
            return
        # If the click is on a fade actor, open the fade-type / delete menu
        # instead of the generic track menu.
        fade = self._fade_under(local_pos)
        if fade is not None:
            self._show_fade_menu(fade, self.mapToGlobal(local_pos))
            return
        # Speed segment right-click: rate picker + delete.
        seg = self._speed_segment_under(local_pos)
        if seg is not None:
            self._show_speed_menu(seg, self.mapToGlobal(local_pos))
            return
        self.context_menu.emit(self.track.id, self.mapToGlobal(local_pos))

    def _speed_segment_under(self, pos: QPoint) -> "SpeedSegment | None":
        """Return the SpeedSegment under ``pos``, or None."""
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        ms = self._x_to_ms(pos.x())
        for seg in self.track.speed_segments:
            if seg.start_ms <= ms < seg.end_ms:
                return seg
        return None

    def _speed_edge_at(self, x: int, y: int) -> "tuple[SpeedSegment | None, str]":
        """Return (seg, 'left'/'right') if the cursor is on a speed
        segment's resize edge, (None, '') otherwise."""
        if y < self.LABEL_H or y > self.LABEL_H + self.TIMELINE_H:
            return None, ""
        for seg in self.track.speed_segments:
            sx1 = self._ms_to_x(seg.start_ms)
            sx2 = self._ms_to_x(seg.end_ms)
            if abs(x - sx1) <= self.SPEED_EDGE_GRAB_PX:
                return seg, "left"
            if abs(x - sx2) <= self.SPEED_EDGE_GRAB_PX:
                return seg, "right"
        return None, ""

    def _show_speed_menu(self, seg: "SpeedSegment", global_pos) -> None:
        """Preset rate picker + delete action for a placed SpeedSegment."""
        menu = QMenu(self)
        # Header (disabled action showing current speed)
        hdr = menu.addAction(tr("veditor.speed_menu.current", speed=_format_speed(seg.speed)))
        hdr.setEnabled(False)
        menu.addSeparator()
        preset_actions: list = []
        for p in SpeedCard.PRESETS:
            a = menu.addAction(SpeedCard._format_preset(p))
            a.setCheckable(True)
            a.setChecked(abs(seg.speed - p) < 1e-3)
            preset_actions.append((a, p))
        menu.addSeparator()
        act_del = menu.addAction(tr("veditor.speed_menu.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_del:
            try:
                self.track.speed_segments.remove(seg)
            except ValueError:
                pass
            self.update()
            self.speed_changed.emit(self.track.id)
            return
        for a, p in preset_actions:
            if chosen is a:
                seg.speed = float(p)
                self.update()
                self.speed_changed.emit(self.track.id)
                return

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
        # Double-click on a typography actor opens the editor; on a
        # fade segment, deletes it.
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        pos = event.position().toPoint()
        typo_actor, _zone = self._typography_at(pos)
        if typo_actor is not None:
            self.typography_double_clicked.emit(self.track.id, typo_actor.id)
            return
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return
        ms = self._x_to_ms(pos.x())
        for fade in list(self.track.fades):
            if fade.contains(ms):
                self.track.fades.remove(fade)
                self.update()
                self.fades_changed.emit(self.track.id)
                return

    # ---------- typography actor painting + hit-test ----------

    def _typography_actor_rect(self, actor, strip_rect: QRect) -> QRect:
        """Rect of a typography actor chip in widget coords. Lives as
        a thin strip at the top of the track's timeline rect."""
        x1 = self._ms_to_x(int(actor.start_ms))
        x2 = self._ms_to_x(int(actor.end_ms))
        w = max(2, x2 - x1)
        return QRect(x1, strip_rect.top() + 2, w, self.TYPO_CHIP_H)

    def _paint_typography_actor(
        self, painter: QPainter, actor, strip_rect: QRect
    ) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush

        r = self._typography_actor_rect(actor, strip_rect)
        if r.width() < 2:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Orange → pink gradient (matches the TypographyCard swatch).
        grad = QLinearGradient(r.left(), 0, r.right(), 0)
        grad.setColorAt(0.0, QColor(216, 90, 48, 210))
        grad.setColorAt(1.0, QColor(184, 63, 173, 210))
        painter.setBrush(QBrush(grad))

        border = QColor("#ff7a4a") if actor.id == self._typo_drag_actor_id else QColor("#D85A30")
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 3, 3)

        # "T" badge + preview (leave room for the 4px edge handles so
        # text doesn't collide with them).
        painter.setPen(QPen(QColor("#FFFFFF")))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(9)
        painter.setFont(f)
        painter.drawText(r.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, "T")
        preview = actor.display_text()
        if len(preview) > 18:
            preview = preview[:18] + "…"
        f.setBold(False)
        painter.setFont(f)
        painter.drawText(
            r.adjusted(20, 0, -8, 0),
            Qt.AlignmentFlag.AlignVCenter,
            preview,
        )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Edge trim handles — base white for contrast against the
        # orange/pink chip; accent to #D85A30 on hover / drag.
        dragging = self._typo_drag_actor_id == actor.id
        hover = self._hover_typo_actor_id == actor.id
        self._paint_edge_handles(
            painter,
            rect_top=r.top(),
            rect_h=r.height(),
            x_left=r.left() + 1,
            x_right=r.right() - 1,
            left_hot=(hover and self._hover_typo_side == "left")
                or (dragging and self._typo_drag_mode == "resize_l"),
            right_hot=(hover and self._hover_typo_side == "right")
                or (dragging and self._typo_drag_mode == "resize_r"),
            dragging=dragging,
            base_color=QColor(255, 255, 255, 220),
            accent_color=QColor("#ff7a4a"),
        )

    def _typography_at(self, pos: QPoint) -> "tuple[object, str]":
        """Return ``(actor, zone)`` at ``pos``. ``zone`` is
        ``"left"`` / ``"right"`` (resize grips) or ``"body"``. When
        nothing matches, ``(None, "")``."""
        strip = self._timeline_rect()
        for actor in reversed(getattr(self.track, "typography_actors", [])):
            r = self._typography_actor_rect(actor, strip)
            if not r.contains(pos):
                continue
            if pos.x() - r.left() <= self.TYPO_EDGE_GRAB_PX:
                return actor, "left"
            if r.right() - pos.x() <= self.TYPO_EDGE_GRAB_PX:
                return actor, "right"
            return actor, "body"
        return None, ""

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
        if md.hasFormat(TEXT_CLIP_MIME):
            event.acceptProposedAction()
            return
        if md.hasFormat(SPEED_MIME_TYPE):
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
        # Typography card drop: add a TextClip actor on this track.
        if md.hasFormat(TEXT_CLIP_MIME):
            if self.track.duration_ms <= 0:
                return
            try:
                duration_ms = int(bytes(md.data(TEXT_CLIP_MIME)).decode("utf-8"))
            except Exception:
                duration_ms = 2000
            duration_ms = max(self.TYPO_MIN_DURATION_MS, duration_ms)
            start = self._x_to_ms(event.position().toPoint().x())
            end = min(self.track.duration_ms, start + duration_ms)
            if end - start < self.TYPO_MIN_DURATION_MS:
                start = max(0, end - self.TYPO_MIN_DURATION_MS)
            if end <= start:
                return
            actor = TextClip(start_ms=start, end_ms=end)
            self.track.typography_actors.append(actor)
            self.track.typography_actors.sort(key=lambda c: c.start_ms)
            self.update()
            self.typography_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return
        # Speed card drop: add a SpeedSegment at the selected rate.
        if md.hasFormat(SPEED_MIME_TYPE):
            if self.track.duration_ms <= 0:
                return
            try:
                payload = bytes(md.data(SPEED_MIME_TYPE)).decode("utf-8")
                speed_str, dur_str = payload.split("|", 1)
                speed = float(speed_str)
                dur_ms = int(dur_str)
            except Exception:
                speed = SpeedCard.DEFAULT_SPEED
                dur_ms = SpeedCard.DEFAULT_DURATION_MS
            dur_ms = max(100, dur_ms)
            center_ms = self._x_to_ms(event.position().toPoint().x())
            start = max(0, center_ms - dur_ms // 2)
            end = min(self.track.duration_ms, start + dur_ms)
            if end <= start:
                return
            # Replace any overlapping speed ranges — we can't have two
            # different speeds on the same source ms.
            self.track.speed_segments = [
                seg for seg in self.track.speed_segments
                if seg.end_ms <= start or seg.start_ms >= end
            ]
            self.track.speed_segments.append(SpeedSegment(start, end, speed))
            self.track.speed_segments.sort(key=lambda s: s.start_ms)
            self.update()
            self.speed_changed.emit(self.track.id)
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


class TypographyCard(QWidget):
    """Draggable "T" card for spawning a TextClip on the typography lane.

    Structure mirrors ``FadeCard``: a compact pill with a visual swatch
    and a label, drag starts a QDrag with ``TEXT_CLIP_MIME`` so the
    receiving lane can distinguish text-clip drops from generic file
    drops or fade-card drops."""

    DEFAULT_DURATION_MS = 2000     # 2-second clip by default

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TypographyCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(120)
        self.setStyleSheet(
            f"""
            QWidget#TypographyCard {{
                background-color: {COLOR_BG_L5};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QWidget#TypographyCard:hover {{
                border-color: #D85A30;
            }}
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 12, 4)
        row.setSpacing(8)

        swatch = _TypographySwatch()
        swatch.setFixedSize(44, 22)
        row.addWidget(swatch)

        title = QLabel(tr("veditor.typo_card.title"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 700;")
        row.addWidget(title)

        self.setToolTip(tr("veditor.typo_card.hint"))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDrag

        mime = QMimeData()
        mime.setData(
            TEXT_CLIP_MIME,
            str(self.DEFAULT_DURATION_MS).encode("utf-8"),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _TypographySwatch(QWidget):
    """Orange-to-pink gradient with a bold "T" glyph — visual identity
    for the TypographyCard. Matches the colour the clip chip paints so
    users recognize the two as the same affordance."""

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush, QFont
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor("#D85A30"))
        grad.setColorAt(1.0, QColor("#B83FAD"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor("#D85A30"), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        painter.setPen(QPen(QColor("#FFFFFF")))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(int(h * 0.55))
        painter.setFont(f)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "T")


class SpeedCard(QWidget):
    """Draggable card for spawning a SpeedSegment on a video track.

    Has a compact speed selector (combo) so the user can pick the rate
    *before* dragging — matches how other NLEs let you pre-configure
    the tool before applying. Drop on a TrackRow creates a 2-second
    segment at the selected speed."""

    DEFAULT_DURATION_MS = 2000
    PRESETS = [0.25, 0.5, 0.75, 1.5, 2.0, 4.0, 8.0, 16.0]
    DEFAULT_SPEED = 2.0

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SpeedCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(150)
        self.setStyleSheet(
            f"""
            QWidget#SpeedCard {{
                background-color: {COLOR_BG_L5};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QWidget#SpeedCard:hover {{
                border-color: #4a9bee;
            }}
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(8)

        swatch = _SpeedSwatch()
        swatch.setFixedSize(44, 22)
        row.addWidget(swatch)

        title = QLabel(tr("veditor.speed_card.title"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 700;")
        row.addWidget(title)

        # Preset selector — don't start a drag when the user clicks
        # inside the combo, only when they grab the body.
        from PySide6.QtWidgets import QComboBox
        self._combo = QComboBox()
        for p in self.PRESETS:
            self._combo.addItem(self._format_preset(p), p)
        self._combo.setCurrentText(self._format_preset(self.DEFAULT_SPEED))
        self._combo.setFixedWidth(64)
        self._combo.setStyleSheet(
            f"QComboBox {{ background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; padding: 2px 6px; }}"
        )
        row.addWidget(self._combo)

        self.setToolTip(tr("veditor.speed_card.hint"))

    @staticmethod
    def _format_preset(p: float) -> str:
        # 2.0 → "2x", 0.5 → "0.5x", 1.5 → "1.5x"
        if abs(p - round(p)) < 1e-3:
            return f"{int(round(p))}x"
        return f"{p:g}x"

    def selected_speed(self) -> float:
        data = self._combo.currentData()
        if isinstance(data, (int, float)) and data > 0:
            return float(data)
        return self.DEFAULT_SPEED

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # Don't steal clicks from the combo — if the user clicked on
        # the combo area, let Qt handle it normally.
        combo_rect = self._combo.geometry()
        if combo_rect.contains(event.position().toPoint()):
            super().mousePressEvent(event)
            return

        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDrag

        payload = f"{self.selected_speed():.6f}|{self.DEFAULT_DURATION_MS}"
        mime = QMimeData()
        mime.setData(SPEED_MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _SpeedSwatch(QWidget):
    """Mini visual for the SpeedCard — three forward-chevrons on a
    blue pad to suggest 'fast forward'."""

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush, QFont, QPolygon
        from PySide6.QtCore import QPoint
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor("#4a9bee"))
        grad.setColorAt(1.0, QColor("#2f6bbf"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor("#4a9bee"), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        # Three chevron arrows ">"
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        tri_w = 5
        cy = h // 2
        # spacing between chevrons
        spacing = 7
        start_x = (w - (3 * spacing - 1)) // 2
        for i in range(3):
            x = start_x + i * spacing
            painter.drawLine(x, cy - tri_w, x + tri_w, cy)
            painter.drawLine(x + tri_w, cy, x, cy + tri_w)


class TextLaneRow(QWidget):
    """Dedicated timeline lane for text clips.

    Sits between the timeline ruler and the video tracks. Renders all
    clips from a ``TextTrack`` as rounded chips with the spec's orange
    → pink gradient, plus an IN / HOLD / OUT timing bar underneath the
    text preview. Handles drag-drop of the TypographyCard, clip moves
    (drag body) and resizes (drag left/right edge), context menu, and
    double-click to open the typography editor."""

    MARGIN = 10                    # matches TimelineRuler.MARGIN
    ROW_HEIGHT = 58
    EDGE_GRIP_PX = 8               # left/right edge zone for resize
    MIN_CLIP_MS = 200              # can't shrink a clip below this

    clip_double_clicked = Signal(int)    # clip_id
    clip_context_menu = Signal(int, object)   # clip_id, QPoint (global)
    clips_changed = Signal()             # geometry / list mutation

    def __init__(self, track: "TextTrack") -> None:
        super().__init__()
        self.track = track
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        self._duration_ms: int = 0

        # Interaction state
        self._hover_clip_id: int | None = None
        self._hover_edge: str | None = None       # "left" / "right" / None
        self._active_clip_id: int | None = None
        self._drag_mode: str | None = None        # "move" / "resize_l" / "resize_r"
        self._drag_anchor_ms: int = 0             # mouse-down project ms
        self._drag_orig_start_ms: int = 0
        self._drag_orig_end_ms: int = 0

        self.setFixedHeight(self.ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.setToolTip(tr("veditor.typo_lane.hint"))

    # ---- scaling / width ----

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self._recalc_width()
        self.update()

    def set_project_duration(self, ms: int) -> None:
        self._duration_ms = max(0, int(ms))
        self._recalc_width()
        self.update()

    def set_min_width(self, w: int) -> None:
        self.setMinimumWidth(max(MIN_TRACK_WIDTH, int(w)))
        self.update()

    def _recalc_width(self) -> None:
        span_ms = max(self._duration_ms, self.track.extent_ms())
        w = int(span_ms / 1000.0 * self._px_per_sec) + 2 * self.MARGIN
        self.setMinimumWidth(max(MIN_TRACK_WIDTH, w))

    # ---- coordinate helpers ----

    def _ms_to_x(self, ms: int) -> int:
        return int(self.MARGIN + max(0, ms) / 1000.0 * self._px_per_sec)

    def _x_to_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def _clip_rect(self, clip: TextClip) -> QRect:
        x0 = self._ms_to_x(clip.start_ms)
        x1 = self._ms_to_x(clip.end_ms)
        return QRect(x0, 6, max(2, x1 - x0), self.ROW_HEIGHT - 12)

    def _hit_clip(self, pos: QPoint) -> tuple[TextClip | None, str]:
        """Return ``(clip, zone)`` for the clip under ``pos``. ``zone``
        is ``"left"`` / ``"right"`` (edge grips) or ``"body"``. When no
        clip matches, ``(None, "")``."""
        # Walk right-to-left so later (stacked-on-top) clips win.
        for clip in reversed(self.track.clips):
            r = self._clip_rect(clip)
            if not r.contains(pos):
                continue
            if pos.x() - r.left() <= self.EDGE_GRIP_PX:
                return clip, "left"
            if r.right() - pos.x() <= self.EDGE_GRIP_PX:
                return clip, "right"
            return clip, "body"
        return None, ""

    # ---- painting ----

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background lane strip — transparent over StripedHost's pattern
        # but with a subtle gradient so the lane reads distinct.
        bg = self.rect()
        painter.fillRect(bg, QColor(0, 0, 0, 40))

        # Faint left-edge indicator so users see this is a timeline row.
        painter.fillRect(0, 0, self.MARGIN, bg.height(), QColor(0, 0, 0, 60))

        # Each clip
        for clip in self.track.clips:
            self._paint_clip(painter, clip)

        # Pro-only export badge — Free users see this whenever the
        # lane has clips, so they understand text is preview-only.
        from app import tier
        if (
            tier.is_locked("export.typography")
            and len(self.track.clips) > 0
        ):
            self._paint_pro_export_badge(painter)

    def _paint_pro_export_badge(self, painter: QPainter) -> None:
        """Right-aligned chip telling Free users typography is
        excluded from export. Painted on top of clips so it stays
        visible even on a busy lane."""
        text = tr("veditor.typo_lane.pro_export_badge")
        f = QFont(painter.font())
        f.setPointSize(9)
        f.setBold(True)
        painter.setFont(f)
        metrics = painter.fontMetrics()
        pad_x, pad_y = 8, 3
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        chip_w = text_w + pad_x * 2
        chip_h = text_h + pad_y * 2
        chip_rect = QRect(
            self.width() - chip_w - 8,
            (self.height() - chip_h) // 2,
            chip_w, chip_h,
        )
        # Chip body — semi-opaque dark with amber border so it reads
        # as "warning / locked" rather than "active".
        painter.setBrush(QColor(20, 20, 28, 220))
        painter.setPen(QPen(QColor("#D8A030"), 1))
        painter.drawRoundedRect(chip_rect, 6, 6)
        painter.setPen(QPen(QColor("#FFD080")))
        painter.drawText(
            chip_rect, Qt.AlignmentFlag.AlignCenter, text,
        )

    def _paint_clip(self, painter: QPainter, clip: TextClip) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush

        r = self._clip_rect(clip)
        if r.width() < 2:
            return

        # Background gradient
        grad = QLinearGradient(r.left(), 0, r.right(), 0)
        grad.setColorAt(0.0, QColor(216, 90, 48, 180))    # orange
        grad.setColorAt(1.0, QColor(184, 63, 173, 180))   # pink
        painter.setBrush(QBrush(grad))

        # Border — brighter when this clip is the active (drag) target
        border = QColor("#ff7a4a") if clip.id == self._active_clip_id else QColor("#D85A30")
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 4, 4)

        # T-icon badge (small) + text preview
        painter.setPen(QPen(QColor("#FFFFFF")))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(10)
        painter.setFont(f)
        painter.drawText(
            r.adjusted(6, 4, -6, -18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "T",
        )

        f.setBold(False)
        f.setPointSize(9)
        painter.setFont(f)
        preview = clip.display_text()
        if len(preview) > 22:
            preview = preview[:22] + "…"
        painter.drawText(
            r.adjusted(20, 4, -6, -18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            preview,
        )

        # IN / HOLD / OUT timing bar at the bottom of the chip
        bar_margin = 5
        bar_rect = QRect(
            r.left() + bar_margin,
            r.bottom() - 8,
            max(1, r.width() - 2 * bar_margin),
            4,
        )
        total_s = max(0.001, clip.duration_s)
        in_ratio = max(0.0, min(1.0, clip.animation.in_duration / total_s))
        out_ratio = max(0.0, min(1.0, clip.animation.out_duration / total_s))
        if in_ratio + out_ratio > 1.0:
            # Protect against shorter-than-animation clips.
            scale = 1.0 / (in_ratio + out_ratio)
            in_ratio *= scale
            out_ratio *= scale

        in_w = int(bar_rect.width() * in_ratio)
        out_w = int(bar_rect.width() * out_ratio)
        hold_w = max(0, bar_rect.width() - in_w - out_w)

        if in_w > 0:
            painter.fillRect(
                QRect(bar_rect.left(), bar_rect.top(), in_w, bar_rect.height()),
                QColor("#5DCAA5"),
            )
        if hold_w > 0:
            painter.fillRect(
                QRect(bar_rect.left() + in_w, bar_rect.top(), hold_w, bar_rect.height()),
                QColor(255, 255, 255, 70),
            )
        if out_w > 0:
            painter.fillRect(
                QRect(bar_rect.right() - out_w, bar_rect.top(), out_w, bar_rect.height()),
                QColor("#D85A30"),
            )

    # ---- mouse interaction ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        clip, zone = self._hit_clip(pos)
        if clip is None:
            return
        self._active_clip_id = clip.id
        self._drag_anchor_ms = self._x_to_ms(pos.x())
        self._drag_orig_start_ms = int(clip.start_ms)
        self._drag_orig_end_ms = int(clip.end_ms)
        if zone == "left":
            self._drag_mode = "resize_l"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zone == "right":
            self._drag_mode = "resize_r"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self._drag_mode = "move"
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._drag_mode and self._active_clip_id is not None:
            clip = self.track.find(self._active_clip_id)
            if clip is None:
                self._drag_mode = None
                return
            delta_ms = self._x_to_ms(pos.x()) - self._drag_anchor_ms
            if self._drag_mode == "move":
                new_start = max(0, self._drag_orig_start_ms + delta_ms)
                duration = self._drag_orig_end_ms - self._drag_orig_start_ms
                clip.start_ms = new_start
                clip.end_ms = new_start + duration
            elif self._drag_mode == "resize_l":
                new_start = max(0, self._drag_orig_start_ms + delta_ms)
                new_start = min(new_start, clip.end_ms - self.MIN_CLIP_MS)
                clip.start_ms = new_start
            elif self._drag_mode == "resize_r":
                new_end = max(
                    clip.start_ms + self.MIN_CLIP_MS,
                    self._drag_orig_end_ms + delta_ms,
                )
                clip.end_ms = new_end
            self._recalc_width()
            self.clips_changed.emit()
            self.update()
            return

        # Idle hover: cursor feedback
        _, zone = self._hit_clip(pos)
        if zone in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zone == "body":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_mode is not None:
            # Sort by start_ms to keep the internal list ordered.
            self.track.clips.sort(key=lambda c: c.start_ms)
            self.clips_changed.emit()
        self._drag_mode = None
        self._active_clip_id = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        clip, _zone = self._hit_clip(pos)
        if clip is not None:
            self.clip_double_clicked.emit(clip.id)

    def contextMenuEvent(self, event) -> None:
        pos = event.pos()
        clip, _zone = self._hit_clip(pos)
        if clip is None:
            event.ignore()
            return
        self.clip_context_menu.emit(clip.id, event.globalPos())
        event.accept()

    # ---- drag-drop (T-card) ----

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(TEXT_CLIP_MIME):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(TEXT_CLIP_MIME):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        if not md.hasFormat(TEXT_CLIP_MIME):
            super().dropEvent(event)
            return
        try:
            duration_ms = int(bytes(md.data(TEXT_CLIP_MIME)).decode("utf-8"))
        except Exception:
            duration_ms = 2000

        drop_ms = self._x_to_ms(event.position().toPoint().x())
        clip = TextClip(
            start_ms=max(0, drop_ms),
            end_ms=max(0, drop_ms) + max(self.MIN_CLIP_MS, duration_ms),
        )
        self.track.add_clip(clip)
        self._recalc_width()
        self.clips_changed.emit()
        self.update()
        event.acceptProposedAction()
        # Hand back the id so the caller can immediately open the editor.
        self.clip_double_clicked.emit(clip.id)


class _TextPreviewItem:
    """Lightweight QGraphicsItem that paints a TextClip preview.

    Implemented via composition with a QGraphicsRectItem so we don't
    need to subclass QGraphicsItem (which is awkward in PySide6 because
    the abstract methods make instantiation finicky).

    ``bg_provider`` is a zero-arg callable returning a QPixmap to paint
    behind the text (the editor uses this to show the video frame at the
    current playhead). Returning ``None`` falls back to a solid black
    backdrop."""

    def __init__(self, clip: TextClip, bg_provider=None, time_provider=None):
        from PySide6.QtWidgets import QGraphicsRectItem
        self.clip = clip
        self._bg_provider = bg_provider
        # ``time_provider`` returns the current playback time (seconds
        # since the clip's start) used to drive the IN/HOLD/OUT
        # animation. Returning ``None`` means "show the static
        # final-state result" (i.e. no animation applied).
        self._time_provider = time_provider

        self._root = QGraphicsRectItem(0, 0, 1920, 1080)
        from PySide6.QtGui import QBrush
        self._root.setBrush(QBrush(QColor("#000")))
        self._root.setPen(QPen(Qt.PenStyle.NoPen))

        # Custom paint via overriding paint() on the rect item — easiest
        # cross-version Qt path.
        original_paint = self._root.paint

        def _paint(painter, option, widget=None):
            original_paint(painter, option, widget)
            self._draw_background(painter)
            self._draw_text(painter)

        self._root.paint = _paint

    def graphics_item(self):
        return self._root

    def refresh(self):
        self._root.update()

    def _draw_background(self, painter: QPainter) -> None:
        if self._bg_provider is None:
            return
        try:
            pm = self._bg_provider()
        except Exception:
            return
        if pm is None or pm.isNull():
            return
        scene_w, scene_h = 1920.0, 1080.0
        pw, ph = pm.width(), pm.height()
        if pw <= 0 or ph <= 0:
            return
        scale = min(scene_w / pw, scene_h / ph)
        draw_w = pw * scale
        draw_h = ph * scale
        ox = (scene_w - draw_w) / 2.0
        oy = (scene_h - draw_h) / 2.0
        painter.drawPixmap(int(ox), int(oy), int(draw_w), int(draw_h), pm)

    def _draw_text(self, painter: QPainter) -> None:
        from PySide6.QtGui import QFontMetrics, QPainterPath
        from app.typo_animations import (
            compute_clip_transform, compute_clip_glyph_transforms,
            compute_clip_layers, TextTransform,
        )
        clip = self.clip
        text = clip.text or "Enter text…"
        style = clip.style

        scene_w, scene_h = 1920.0, 1080.0
        cx = float(style.position_x) * scene_w
        cy = float(style.position_y) * scene_h

        # Resolve play time; ``None`` = paused (steady HOLD state).
        play_time = None
        if self._time_provider is not None:
            play_time = self._time_provider()

        # Multi-layer dispatch (RGB split / glitch animations) — drawn
        # once per layer with each layer's color + offset.
        if play_time is not None:
            layers = compute_clip_layers(clip, float(play_time))
            if layers is not None:
                self._draw_text_layers(painter, text, style, cx, cy, layers)
                return

        # Per-glyph dispatch: if the active animation is per-glyph,
        # rendering branches into a different path that iterates each
        # character with its own transform around its own pivot.
        glyph_xfs = None
        if play_time is not None:
            glyph_xfs = compute_clip_glyph_transforms(
                clip, float(play_time), len(text or "")
            )
        if glyph_xfs is not None:
            self._draw_text_perglyph(painter, text, style, cx, cy, glyph_xfs)
            return

        # Whole-text fast path.
        if play_time is not None:
            xf = compute_clip_transform(clip, float(play_time)) or TextTransform.identity()
        else:
            xf = TextTransform.identity()

        # Apply opacity globally for the text drawing block; geometric
        # transform pivots on the text's center (cx, cy).
        painter.save()
        painter.setOpacity(max(0.0, min(1.0, xf.opacity)))
        painter.translate(cx + xf.offset_x, cy + xf.offset_y)
        if abs(xf.rotation_deg) > 0.05:
            painter.rotate(xf.rotation_deg)
        if abs(xf.scale_x - 1.0) > 1e-3 or abs(xf.scale_y - 1.0) > 1e-3:
            painter.scale(xf.scale_x, xf.scale_y)
        painter.translate(-cx, -cy)

        font = QFont(style.font_family, int(style.font_size))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        if style.letter_spacing:
            from PySide6.QtGui import QFont as _QFont
            font.setLetterSpacing(_QFont.SpacingType.AbsoluteSpacing,
                                  float(style.letter_spacing))
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Multi-line: split on newlines, render line-by-line.
        lines = text.split("\n") if text else [text]
        line_h = int(fm.height() * float(style.line_height))
        total_h = max(line_h, line_h * len(lines))

        # Top-left of the text block
        widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
        block_x = cx - widest / 2.0
        block_y = cy - total_h / 2.0

        # Background rect
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(block_x - pad), int(block_y - pad),
                int(widest + 2 * pad), int(total_h + 2 * pad),
                radius, radius,
            )

        # For each line: shadow → outline → fill
        for i, ln in enumerate(lines):
            ln_w = fm.horizontalAdvance(ln)
            # Honor alignment within the bounding block.
            if style.alignment == "left":
                lx = block_x
            elif style.alignment == "right":
                lx = block_x + (widest - ln_w)
            else:
                lx = block_x + (widest - ln_w) / 2.0
            ly = block_y + i * line_h + fm.ascent()

            # Shadow
            if style.shadow_color and (style.shadow_offset_x or style.shadow_offset_y):
                painter.setPen(QColor(style.shadow_color))
                painter.drawText(
                    int(lx + style.shadow_offset_x),
                    int(ly + style.shadow_offset_y),
                    ln,
                )

            # Outline
            if style.outline_color and style.outline_width and style.outline_width > 0:
                path = QPainterPath()
                path.addText(lx, ly, font, ln)
                pen = QPen(QColor(style.outline_color))
                pen.setWidth(int(style.outline_width))
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            # Fill
            painter.setPen(QColor(style.color or "#FFFFFF"))
            painter.drawText(int(lx), int(ly), ln)

        # Close the save() that opened the animation transform block.
        painter.restore()

    def _draw_text_perglyph(
        self, painter: QPainter, text: str, style, cx: float, cy: float,
        glyph_xfs: list,
    ) -> None:
        """Render a Folding-style per-glyph animation. Each char gets
        its own transform around its own pivot. Effects (shadow /
        outline / fill) are drawn per-character so rotation pivots
        stay correct."""
        from PySide6.QtGui import QFontMetrics, QPainterPath

        font = QFont(style.font_family, int(style.font_size))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        if style.letter_spacing:
            font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing,
                float(style.letter_spacing),
            )
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Lay out chars by line (multi-line text — newlines split).
        # Per-glyph animations don't make as much sense for multi-line,
        # but we still place them sensibly.
        lines = text.split("\n") if text else [text]
        line_h = int(fm.height() * float(style.line_height))
        total_h = max(line_h, line_h * len(lines))

        widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
        block_x = cx - widest / 2.0
        block_y = cy - total_h / 2.0

        # Background rect (drawn once, behind every glyph)
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(block_x - pad), int(block_y - pad),
                int(widest + 2 * pad), int(total_h + 2 * pad),
                radius, radius,
            )

        # Walk every char in order, mapping it to the i-th transform.
        # Newlines bump the cursor to the next line and don't consume
        # an entry from glyph_xfs (the animation generator received the
        # full character count including \n; we just skip the visible
        # render for \n). Keep the indices aligned by iterating with i.
        char_idx = 0
        for line_no, ln in enumerate(lines):
            ln_w = fm.horizontalAdvance(ln)
            if style.alignment == "left":
                lx = block_x
            elif style.alignment == "right":
                lx = block_x + (widest - ln_w)
            else:
                lx = block_x + (widest - ln_w) / 2.0
            ly = block_y + line_no * line_h + fm.ascent()

            cursor_x = lx
            for ch in ln:
                gx = cursor_x
                gw = fm.horizontalAdvance(ch)
                if char_idx >= len(glyph_xfs):
                    xf = glyph_xfs[-1] if glyph_xfs else None
                else:
                    xf = glyph_xfs[char_idx]
                char_idx += 1

                if xf is None or ch.strip() == "":
                    # Whitespace still advances the cursor but we don't
                    # bother drawing.
                    cursor_x += gw
                    continue

                pivot_px_x = gx + gw * float(xf.pivot_x)
                # pivot_y: 0=top of glyph (above baseline), 1=bottom.
                # baseline is at ly; ascent above, descent below.
                pivot_px_y = (ly - fm.ascent()) + fm.height() * float(xf.pivot_y)

                painter.save()
                painter.setOpacity(max(0.0, min(1.0, xf.opacity)))
                painter.translate(
                    pivot_px_x + xf.offset_x,
                    pivot_px_y + xf.offset_y,
                )
                if abs(xf.rotation_deg) > 0.05:
                    painter.rotate(xf.rotation_deg)
                if abs(xf.scale_x - 1.0) > 1e-3 or abs(xf.scale_y - 1.0) > 1e-3:
                    painter.scale(xf.scale_x, xf.scale_y)
                painter.translate(-pivot_px_x, -pivot_px_y)

                # Shadow (per char)
                if style.shadow_color and (style.shadow_offset_x or style.shadow_offset_y):
                    painter.setPen(QColor(style.shadow_color))
                    painter.drawText(
                        int(gx + style.shadow_offset_x),
                        int(ly + style.shadow_offset_y),
                        ch,
                    )

                # Outline
                if style.outline_color and style.outline_width and style.outline_width > 0:
                    path = QPainterPath()
                    path.addText(gx, ly, font, ch)
                    pen = QPen(QColor(style.outline_color))
                    pen.setWidth(int(style.outline_width))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)

                # Fill — honor color override if the glyph carries one,
                # unless the user has locked the clip to a single color.
                if getattr(self.clip.animation, "mono_color", False):
                    fill_color = style.color or "#FFFFFF"
                else:
                    fill_color = xf.color_override or style.color or "#FFFFFF"
                painter.setPen(QColor(fill_color))
                painter.drawText(int(gx), int(ly), ch)

                painter.restore()
                cursor_x += gw
            # Skip the implicit \n character index when there are
            # multiple lines — the global character count we pass to
            # the animation generator includes \n delimiters.
            if line_no < len(lines) - 1:
                char_idx += 1

    def _draw_text_layers(
        self, painter: QPainter, text: str, style, cx: float, cy: float,
        layers: list,
    ) -> None:
        """Multi-layer rendering — re-draws the entire text once per
        LayerTransform (different colour + offset). Used by glitch /
        RGB-split style animations."""
        from PySide6.QtGui import QFontMetrics, QPainterPath

        font = QFont(style.font_family, int(style.font_size))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        if style.letter_spacing:
            font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing,
                float(style.letter_spacing),
            )
        painter.setFont(font)
        fm = QFontMetrics(font)

        lines = text.split("\n") if text else [text]
        line_h = int(fm.height() * float(style.line_height))
        total_h = max(line_h, line_h * len(lines))
        widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
        block_x = cx - widest / 2.0
        block_y = cy - total_h / 2.0

        # Background rect drawn once (under all layers).
        if style.background_color:
            pad = max(0, int(style.background_padding))
            radius = max(0, int(style.background_radius))
            painter.setBrush(QColor(style.background_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(block_x - pad), int(block_y - pad),
                int(widest + 2 * pad), int(total_h + 2 * pad),
                radius, radius,
            )

        # Iterate layers back-to-front. Mono-color flag forces every
        # layer to honor style.color (effectively collapsing the RGB
        # split — useful when users want the glitch motion without
        # the chromatic aberration).
        mono = bool(getattr(self.clip.animation, "mono_color", False))
        for layer in layers:
            painter.save()
            painter.setOpacity(max(0.0, min(1.0, layer.opacity)))
            painter.translate(layer.offset_x, layer.offset_y)

            if mono:
                fill_color = style.color or "#FFFFFF"
            else:
                fill_color = layer.color_override or style.color or "#FFFFFF"

            for i, ln in enumerate(lines):
                ln_w = fm.horizontalAdvance(ln)
                if style.alignment == "left":
                    lx = block_x
                elif style.alignment == "right":
                    lx = block_x + (widest - ln_w)
                else:
                    lx = block_x + (widest - ln_w) / 2.0
                ly = block_y + i * line_h + fm.ascent()

                # Outline only on the topmost layer (last iteration)
                # so the chromatic split stays visible underneath.
                is_top = layer is layers[-1]
                if is_top and style.outline_color and style.outline_width and style.outline_width > 0:
                    path = QPainterPath()
                    path.addText(lx, ly, font, ln)
                    pen = QPen(QColor(style.outline_color))
                    pen.setWidth(int(style.outline_width))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)

                painter.setPen(QColor(fill_color))
                painter.drawText(int(lx), int(ly), ln)

            painter.restore()


class _PreviewView(QScrollArea):
    """Wraps a QGraphicsView; re-fits scene to view on resize."""

    def __init__(self):
        from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        self._scene = QGraphicsScene(0, 0, 1920, 1080)
        from PySide6.QtGui import QBrush
        self._scene.setBackgroundBrush(QBrush(QColor("#000")))
        self._gview = QGraphicsView(self._scene)
        self._gview.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._gview.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self._gview.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._gview.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gview.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._gview.setStyleSheet("QGraphicsView { background-color: #000; border: none; }")
        self.setWidget(self._gview)

    def add_item(self, item):
        self._scene.addItem(item)

    def fit(self):
        self._gview.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def showEvent(self, event):
        super().showEvent(event)
        self.fit()


class _FontPickerDelegate:
    """Item delegate factory for the font list. Each row shows the
    family name in the default UI font (so users can read the name
    even when the font itself has no Latin glyphs), plus a sample
    string rendered IN the actual font."""

    SAMPLE_TEXT = "Aa Bb 한글 漢字 1234"
    ROW_HEIGHT = 40

    @classmethod
    def install(cls, list_widget) -> None:
        """Attach a QStyledItemDelegate on the given QListWidget."""
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QStyledItemDelegate, QStyle

        class _Delegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                painter.save()
                family = index.data(Qt.ItemDataRole.DisplayRole) or ""
                kind = index.data(Qt.ItemDataRole.UserRole) or "font"

                # Background
                if option.state & QStyle.StateFlag.State_Selected:
                    painter.fillRect(option.rect, QColor(COLOR_ACCENT_BLUE))
                    name_color = QColor(COLOR_TEXT_PRIMARY)
                    sample_color = QColor(COLOR_TEXT_PRIMARY)
                else:
                    painter.fillRect(option.rect, QColor(COLOR_BG_L4))
                    name_color = QColor(COLOR_TEXT_TERTIARY)
                    sample_color = QColor(COLOR_TEXT_PRIMARY)

                if kind == "header":
                    # Section header (non-selectable)
                    f = QFont()
                    f.setBold(True)
                    f.setPointSize(8)
                    painter.setFont(f)
                    painter.setPen(QColor(COLOR_TEXT_TERTIARY))
                    painter.drawText(
                        option.rect.adjusted(10, 0, -8, 0),
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        family,
                    )
                    painter.restore()
                    return

                # Top line: family name in the default UI font (small).
                name_font = QFont()
                name_font.setPointSize(8)
                painter.setFont(name_font)
                painter.setPen(name_color)
                painter.drawText(
                    option.rect.adjusted(10, 3, -8, 0),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    family,
                )

                # Bottom line: sample text rendered in this font.
                sample_font = QFont(family, 12)
                painter.setFont(sample_font)
                painter.setPen(sample_color)
                painter.drawText(
                    option.rect.adjusted(10, 16, -8, -3),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    _FontPickerDelegate.SAMPLE_TEXT,
                )
                painter.restore()

            def sizeHint(self, option, index):
                kind = index.data(Qt.ItemDataRole.UserRole)
                if kind == "header":
                    return QSize(200, 22)
                return QSize(200, _FontPickerDelegate.ROW_HEIGHT)

        delegate = _Delegate(list_widget)
        list_widget.setItemDelegate(delegate)
        # Keep a reference so the delegate isn't GC'd when our caller
        # returns — Qt only takes a weak handle.
        list_widget._delegate_ref = delegate


class _FontPickerButton(QWidget):
    """Compact font picker: a button that shows the current family
    rendered in its own typeface, plus a ▾ chevron. Clicking opens a
    popup frame (anchored below the button) with a search field and
    the same scrollable list used in the previous implementation.
    Selection commits the change and closes the popup."""

    font_changed = Signal(str)

    PINNED_FONTS = (
        "Pretendard",
        "Noto Sans KR",
        "Noto Serif KR",
        "Nanum Myeongjo",
        "Gaegu",
        "Noto Sans JP",
        "Noto Serif JP",
        "Shippori Mincho",
        "Arial",
        "Segoe UI",
        "Impact",
    )

    def __init__(self, current_family: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._family = current_family
        self._popup: QWidget | None = None
        self._list = None
        self._search = None

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton()
        self._btn.setObjectName("FontPickerBtn")
        self._btn.setMinimumHeight(36)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

        self._update_btn_label()

    def current_family(self) -> str:
        return self._family

    def set_family(self, family: str) -> None:
        if family != self._family:
            self._family = family
            self._update_btn_label()

    def _update_btn_label(self) -> None:
        f = QFont(self._family, 11)
        self._btn.setFont(f)
        self._btn.setStyleSheet(
            f"QPushButton#FontPickerBtn {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 6px 10px; text-align: left; }}"
            f"QPushButton#FontPickerBtn:hover {{ border-color: #6a6a72; }}"
        )
        # Right-arrow chevron at the right edge.
        self._btn.setText(f"{self._family}     ▾")

    # ---- popup ----

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        from PySide6.QtCore import QTimer
        if self._popup is None:
            self._build_popup()
        # Position the popup just below the button, matching its width
        # (with a sensible minimum so the list is usable).
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 320)
        self._popup.resize(target_w, 380)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()
        QTimer.singleShot(0, self._scroll_to_current)

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import QFrame, QLineEdit, QListWidget, QListWidgetItem
        from PySide6.QtGui import QFontDatabase

        # WindowType.Popup makes the frame auto-dismiss on outside
        # clicks and not steal focus from its parent dialog.
        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("FontPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#FontPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.font_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {COLOR_BG_L4}; "
            f"color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        _FontPickerDelegate.install(self._list)
        v.addWidget(self._list, 1)

        # Populate
        available = set(QFontDatabase.families())
        used: set[str] = set()
        pinned = [f for f in self.PINNED_FONTS if f in available]
        if pinned:
            hdr = QListWidgetItem(tr("veditor.typo_editor.font_recommended"))
            hdr.setData(Qt.ItemDataRole.UserRole, "header")
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(hdr)
            for fam in pinned:
                used.add(fam)
                it = QListWidgetItem(fam)
                self._list.addItem(it)
                if fam == self._family:
                    self._list.setCurrentItem(it)
        all_hdr = QListWidgetItem(tr("veditor.typo_editor.font_all"))
        all_hdr.setData(Qt.ItemDataRole.UserRole, "header")
        all_hdr.setFlags(Qt.ItemFlag.NoItemFlags)
        self._list.addItem(all_hdr)
        for fam in sorted(available):
            if fam in used:
                continue
            it = QListWidgetItem(fam)
            self._list.addItem(it)
            if fam == self._family:
                self._list.setCurrentItem(it)

        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemActivated.connect(self._on_item_clicked)

    def _on_item_clicked(self, item) -> None:
        if item is None:
            return
        if item.data(Qt.ItemDataRole.UserRole) == "header":
            return
        self._family = item.text()
        self._update_btn_label()
        if self._popup is not None:
            self._popup.hide()
        self.font_changed.emit(self._family)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        for i in range(self._list.count()):
            it = self._list.item(i)
            kind = it.data(Qt.ItemDataRole.UserRole)
            if kind == "header":
                it.setHidden(bool(needle))
                continue
            it.setHidden(bool(needle) and needle not in it.text().lower())

    def _scroll_to_current(self) -> None:
        if self._list is None:
            return
        cur = self._list.currentItem()
        if cur is not None:
            self._list.scrollToItem(
                cur, self._list.ScrollHint.PositionAtCenter,
            )


class _ColorWheelWidget(QWidget):
    """DaVinci-style chromaticity wheel with a draggable indicator.

    Emits ``value_changed(x, y)`` in ``-100..100`` while dragging.
    Axis convention matches :func:`app.color_grading._wheel_to_rgb_offset`:

        +x → red / orange (warm)        -x → cyan / blue  (cool)
        +y → magenta                    -y → green

    Visual treatment: smooth 12-stop conical hue ring with a subtle
    outer glow, a feathered radial centre fade for the neutral zone,
    two faint guide rings at 50 % and 100 % saturation, a crosshair,
    and a high-contrast white indicator with an inner colour dot.
    Bottom label sits directly under the wheel, with the live ``x, y``
    readout in a small chip just above the label.
    """

    value_changed = Signal(int, int)

    SIZE = 96               # widget side length (px) — tighter than v1
    LABEL_H = 16
    READOUT_H = 13
    INDICATOR_R = 6

    def __init__(self, label: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._x = 0           # -100..100
        self._y = 0
        self._dragging = False
        # Total height = wheel + readout + label + small gaps.
        self.setFixedSize(self.SIZE, self.SIZE + self.READOUT_H + self.LABEL_H + 4)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def value(self) -> tuple[int, int]:
        return self._x, self._y

    def set_value(self, x: int, y: int, *, emit: bool = True) -> None:
        x = max(-100, min(100, int(x)))
        y = max(-100, min(100, int(y)))
        if x == self._x and y == self._y:
            return
        self._x = x
        self._y = y
        self.update()
        if emit:
            self.value_changed.emit(self._x, self._y)

    # ---- geometry helpers ----

    def _wheel_rect(self) -> QRect:
        # Leave room at the bottom for readout + label.
        return QRect(3, 3, self.SIZE - 6, self.SIZE - 6)

    def _wheel_center(self) -> QPoint:
        r = self._wheel_rect()
        return QPoint(r.left() + r.width() // 2,
                      r.top() + r.height() // 2)

    def _wheel_radius(self) -> float:
        r = self._wheel_rect()
        return min(r.width(), r.height()) / 2.0 - 2.0

    def _value_to_pos(self) -> QPoint:
        c = self._wheel_center()
        rad = self._wheel_radius()
        x = c.x() + self._x / 100.0 * rad
        y = c.y() + self._y / 100.0 * rad
        return QPoint(int(x), int(y))

    def _pos_to_value(self, p: QPoint) -> tuple[int, int]:
        c = self._wheel_center()
        rad = self._wheel_radius()
        if rad <= 0:
            return 0, 0
        dx = (p.x() - c.x()) / rad
        dy = (p.y() - c.y()) / rad
        import math
        d = math.hypot(dx, dy)
        if d > 1.0:
            dx /= d
            dy /= d
        x = int(round(max(-1.0, min(1.0, dx)) * 100))
        y = int(round(max(-1.0, min(1.0, dy)) * 100))
        return x, y

    # ---- mouse ----

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            x, y = self._pos_to_value(event.pos())
            self.set_value(x, y)
        elif event.button() == Qt.MouseButton.RightButton:
            self.set_value(0, 0)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            x, y = self._pos_to_value(event.pos())
            self.set_value(x, y)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def mouseDoubleClickEvent(self, _event) -> None:
        self.set_value(0, 0)

    # ---- painting ----

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QConicalGradient, QRadialGradient
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        wheel = self._wheel_rect()
        cx = wheel.center().x()
        cy = wheel.center().y()
        rad = self._wheel_radius()

        # ---- subtle outer glow (drawn first, behind everything) ----
        glow = QRadialGradient(QPoint(cx, cy), rad + 6)
        glow.setColorAt(0.85, QColor(0, 0, 0, 0))
        glow.setColorAt(1.00, QColor(0, 0, 0, 90))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cx, cy), int(rad + 5), int(rad + 5))

        # ---- conical hue ring ----
        # QConicalGradient progresses counter-clockwise from the 3 o'clock
        # position. To match the value convention (+x=warm red,
        # -y=green at the screen top, -x=cyan, +y=magenta at the screen
        # bottom), place red at t=0, green at t=0.25, cyan at 0.5,
        # magenta at 0.75.
        grad = QConicalGradient(QPoint(cx, cy), 0.0)
        stops = [
            (0.000, (245,  70,  70)),    # red       — 3 o'clock, +x
            (0.083, (245, 150,  60)),    # orange
            (0.166, (235, 210,  60)),    # yellow
            (0.250, (110, 220,  70)),    # GREEN     — 12 o'clock, -y
            (0.333, ( 60, 220, 140)),    # green-cyan
            (0.416, ( 50, 210, 200)),    # cyan-green
            (0.500, ( 60, 180, 220)),    # CYAN      — 9 o'clock, -x
            (0.583, ( 80, 140, 235)),    # blue
            (0.666, (130, 100, 235)),    # blue-violet
            (0.750, (235,  90, 200)),    # MAGENTA   — 6 o'clock, +y
            (0.833, (240, 100, 150)),    # pink
            (0.916, (245,  90, 110)),    # warm pink
            (1.000, (245,  70,  70)),
        ]
        for stop, (r, g, b) in stops:
            grad.setColorAt(stop, QColor(r, g, b))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(wheel)

        # ---- feathered radial fade toward neutral grey at centre ----
        # Two-stop fade gives the wheel that "punched" centre look
        # without obliterating chromatic information at the edge.
        radial = QRadialGradient(QPoint(cx, cy), rad)
        radial.setColorAt(0.00, QColor(232, 232, 234, 245))
        radial.setColorAt(0.35, QColor(232, 232, 234, 130))
        radial.setColorAt(0.65, QColor(232, 232, 234, 0))
        painter.setBrush(radial)
        painter.drawEllipse(wheel)

        # ---- guide rings at 50% and 100% saturation ----
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawEllipse(QPoint(cx, cy), int(rad * 0.5), int(rad * 0.5))
        # 100% ring (rim) — slightly darker to read as the boundary.
        painter.setPen(QPen(QColor(0, 0, 0, 130), 1))
        painter.drawEllipse(wheel)

        # ---- crosshair ----
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawLine(cx - 4, cy, cx + 4, cy)
        painter.drawLine(cx, cy - 4, cx, cy + 4)

        # ---- indicator ----
        # White ring + coloured inner dot. The dot's hue matches the
        # current (x, y) direction so the user can see "what colour
        # am I pulling toward". Saturation = distance from centre.
        ind = self._value_to_pos()
        # Outer ring (with subtle drop shadow).
        painter.setPen(QPen(QColor(0, 0, 0, 110), 1))
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(ind, self.INDICATOR_R, self.INDICATOR_R)
        # Inner coloured dot — sample the wheel colour at this position.
        inner_color = self._sample_wheel_color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(inner_color)
        painter.drawEllipse(ind, self.INDICATOR_R - 3, self.INDICATOR_R - 3)

        # ---- numeric readout ----
        readout_text = f"{self._x:+d}, {self._y:+d}"
        painter.setPen(QPen(QColor("#9CA0AC")))
        f = QFont(painter.font())
        f.setPointSize(8)
        painter.setFont(f)
        painter.drawText(
            QRect(0, self.SIZE - 3, self.width(), self.READOUT_H),
            Qt.AlignmentFlag.AlignCenter,
            readout_text,
        )

        # ---- bottom label ----
        painter.setPen(QPen(QColor("#D6D6DC")))
        f.setPointSize(9)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(
            QRect(0, self.SIZE + self.READOUT_H, self.width(), self.LABEL_H),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )

    def _sample_wheel_color(self) -> QColor:
        """Approximate the wheel hue at the current (x, y). Used as the
        indicator's inner-dot colour so the user gets visual feedback
        on which way they're pulling. Uses the same 13-stop hue ring
        the gradient paints, with the screen-Y flip baked into the
        atan2 → t conversion (Qt's CCW gradient on a Y-down canvas)."""
        import math
        if self._x == 0 and self._y == 0:
            return QColor(220, 220, 220)
        # Negate the angle: Qt paints the gradient CCW visually, so a
        # point with screen-Y = +y_data lands further around the wheel
        # in the "going CW visually" direction. The negation aligns the
        # sampled colour with the painted gradient.
        ang = math.atan2(self._y, self._x)
        t = (-ang / (2 * math.pi)) % 1.0
        stops = [
            (0.000, (245,  70,  70)),
            (0.083, (245, 150,  60)),
            (0.166, (235, 210,  60)),
            (0.250, (110, 220,  70)),
            (0.333, ( 60, 220, 140)),
            (0.416, ( 50, 210, 200)),
            (0.500, ( 60, 180, 220)),
            (0.583, ( 80, 140, 235)),
            (0.666, (130, 100, 235)),
            (0.750, (235,  90, 200)),
            (0.833, (240, 100, 150)),
            (0.916, (245,  90, 110)),
            (1.000, (245,  70,  70)),
        ]
        for i in range(len(stops) - 1):
            a, ca = stops[i]
            b, cb = stops[i + 1]
            if a <= t <= b:
                u = (t - a) / max(1e-6, b - a)
                r = int(ca[0] + (cb[0] - ca[0]) * u)
                g = int(ca[1] + (cb[1] - ca[1]) * u)
                bl = int(ca[2] + (cb[2] - ca[2]) * u)
                # Saturation = distance from centre.
                d = min(1.0, math.hypot(self._x, self._y) / 100.0)
                rr = int(220 + (r - 220) * d)
                gg = int(220 + (g - 220) * d)
                bb = int(220 + (bl - 220) * d)
                return QColor(rr, gg, bb)
        return QColor(220, 220, 220)


class _AnimationPickerButton(QWidget):
    """Compact animation picker — button shows the current animation's
    name + icon, click opens a popup with category tabs and a 3-column
    tile grid. Scales for the 50+ presets coming in Phase 4."""

    animation_changed = Signal(str)        # animation id

    CATEGORIES = ("basic", "kinetic", "folding", "hold")     # extended in Phase 4

    def __init__(self, current_id: str, direction: str,
                 parent: QWidget | None = None,
                 extras_mode: bool = False) -> None:
        super().__init__(parent)
        self._direction = direction        # "in" / "out" / "hold"
        self._current_id = current_id
        self._popup: QWidget | None = None
        # In extras mode the button never reflects the picked animation
        # — it stays as a "+ Add modifier" trigger and emits the signal
        # so the parent can append to its extras list.
        self._extras_mode = bool(extras_mode)

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton()
        self._btn.setObjectName("AnimPickerBtn")
        self._btn.setMinimumHeight(36)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

        self._update_btn_label()

    def current_id(self) -> str:
        return self._current_id

    def set_current(self, anim_id: str) -> None:
        if anim_id != self._current_id:
            self._current_id = anim_id
            self._update_btn_label()

    def _update_btn_label(self) -> None:
        if self._extras_mode:
            self._btn.setText("  ＋  " + tr("veditor.typo_editor.modifier.add"))
            self._btn.setMinimumHeight(28)
            self._btn.setStyleSheet(
                f"QPushButton#AnimPickerBtn {{ "
                f"background-color: transparent; color: {COLOR_TEXT_TERTIARY}; "
                f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
                f"padding: 4px 10px; text-align: left; font-size: 11px; }}"
                f"QPushButton#AnimPickerBtn:hover {{ "
                f"border-color: #6a6a72; color: {COLOR_TEXT_PRIMARY}; }}"
            )
            return
        from app.typo_animations import get_animation
        anim = get_animation(self._current_id)
        name = tr(anim.name_key)
        self._btn.setText(f" {anim.icon}   {name}     ▾")
        self._btn.setStyleSheet(
            f"QPushButton#AnimPickerBtn {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 6px 10px; text-align: left; font-size: 12px; }}"
            f"QPushButton#AnimPickerBtn:hover {{ border-color: #6a6a72; }}"
        )

    # ---- popup ----

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        if self._popup is None:
            self._build_popup()
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 460)
        self._popup.resize(target_w, 360)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import (
            QFrame, QLineEdit, QTabWidget, QScrollArea, QGridLayout,
        )
        from app.typo_animations import REGISTRY

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("AnimPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#AnimPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.anim_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 4px; top: -1px; }}"
            f"QTabBar::tab {{ background: {COLOR_BG_L4}; color: {COLOR_TEXT_SECONDARY}; "
            f"padding: 6px 12px; border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-bottom: none; border-top-left-radius: 4px; "
            f"border-top-right-radius: 4px; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{ background: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        v.addWidget(self._tabs, 1)

        # All-tab + per-category tabs
        self._tile_buttons: list = []  # references to keep them alive
        # "All" tab first — flat grid
        self._add_tab(
            tr("veditor.typo_editor.anim_cat.all"),
            [a for a in REGISTRY.values()
             if a.direction in (self._direction, "any")],
        )
        for cat in self.CATEGORIES:
            anims = [
                a for a in REGISTRY.values()
                if a.category == cat
                and a.direction in (self._direction, "any")
            ]
            if anims:
                self._add_tab(tr(f"veditor.typo_editor.anim_cat.{cat}"), anims)

    def _add_tab(self, label: str, anims: list) -> None:
        from PySide6.QtWidgets import (
            QScrollArea, QGridLayout,
        )
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)
        scroll.setWidget(grid_host)

        cols = 3
        for idx, anim in enumerate(anims):
            tile = self._make_tile(anim)
            grid.addWidget(tile, idx // cols, idx % cols)
            self._tile_buttons.append(tile)
        # Spacer at bottom
        grid.setRowStretch(grid.rowCount(), 1)

        self._tabs.addTab(page, label)

    def _make_tile(self, anim) -> QWidget:
        """One animation tile in the grid: bordered box with icon at
        top + name at bottom. Click selects + closes the popup."""
        tile = QPushButton()
        tile.setProperty("anim_id", anim.id)
        tile.setProperty("anim_search", f"{tr(anim.name_key)} {anim.id}")
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setMinimumSize(130, 80)
        tile.setMaximumHeight(96)
        is_current = anim.id == self._current_id
        tile.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: {COLOR_BG_L4}; "
            f"color: {COLOR_TEXT_PRIMARY}; "
            f"border: 2px solid "
            f"{COLOR_ACCENT_BLUE if is_current else COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; }}"
            f"QPushButton:hover {{ border-color: #6a6a72; "
            f"background-color: #34343c; }}"
        )
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        icon = QLabel(anim.icon)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 28px; background: transparent; "
            f"border: none;"
        )
        layout.addWidget(icon, 1)
        name = QLabel(tr(anim.name_key))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setWordWrap(True)
        name.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px; "
            f"font-weight: 600; background: transparent; border: none;"
        )
        layout.addWidget(name, 0)

        tile.clicked.connect(lambda _c=False, aid=anim.id: self._select(aid))
        return tile

    def _select(self, anim_id: str) -> None:
        if not self._extras_mode:
            self._current_id = anim_id
            self._update_btn_label()
        if self._popup is not None:
            self._popup.hide()
        self.animation_changed.emit(anim_id)

    def _filter(self, text: str) -> None:
        """Hide tiles whose name or id doesn't contain ``text``."""
        needle = text.lower().strip()
        for tile in self._tile_buttons:
            haystack = (tile.property("anim_search") or "").lower()
            tile.setVisible(not needle or needle in haystack)


class _PresetPickerButton(QWidget):
    """Top-of-dialog preset picker. Click → popup with category tabs +
    tile grid. Selecting a preset emits ``preset_applied(preset_id)``,
    which the dialog uses to overwrite animation + style fields and
    rebuild the editor controls."""

    preset_applied = Signal(str)

    CATEGORIES = ("kinetic", "utaite", "korean", "devila")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup: QWidget | None = None
        self._tile_buttons: list = []

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._btn = QPushButton(tr("veditor.typo_editor.preset_btn"))
        self._btn.setObjectName("PresetPickerBtn")
        self._btn.setMinimumHeight(34)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton#PresetPickerBtn {{ "
            f"background-color: #6a3cb5; color: {COLOR_TEXT_PRIMARY}; "
            f"border: none; border-radius: 4px; "
            f"padding: 6px 14px; font-weight: 700; font-size: 12px; }}"
            f"QPushButton#PresetPickerBtn:hover {{ background-color: #7b4ac9; }}"
        )
        self._btn.clicked.connect(self._toggle_popup)
        h.addWidget(self._btn, 1)

    def _toggle_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        self._open_popup()

    def _open_popup(self) -> None:
        if self._popup is None:
            self._build_popup()
        global_pos = self._btn.mapToGlobal(QPoint(0, self._btn.height() + 2))
        target_w = max(self._btn.width(), 520)
        self._popup.resize(target_w, 380)
        self._popup.move(global_pos)
        self._search.clear()
        self._popup.show()
        self._popup.raise_()
        self._search.setFocus()

    def _build_popup(self) -> None:
        from PySide6.QtWidgets import (
            QFrame, QLineEdit, QTabWidget, QScrollArea, QGridLayout,
        )
        from app.typo_presets import list_presets

        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("PresetPickerPopup")
        self._popup.setStyleSheet(
            f"QFrame#PresetPickerPopup {{ background-color: {COLOR_BG_L3}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        v = QVBoxLayout(self._popup)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("veditor.typo_editor.preset_search"))
        self._search.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; font-size: 11px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._search.textChanged.connect(self._filter)
        v.addWidget(self._search)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 4px; top: -1px; }}"
            f"QTabBar::tab {{ background: {COLOR_BG_L4}; color: {COLOR_TEXT_SECONDARY}; "
            f"padding: 6px 12px; border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-bottom: none; border-top-left-radius: 4px; "
            f"border-top-right-radius: 4px; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{ background: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
        )
        v.addWidget(self._tabs, 1)

        # All tab + per-category
        self._add_tab(tr("veditor.typo_editor.preset_cat.all"), list_presets())
        for cat in self.CATEGORIES:
            anims = list_presets(cat)
            if anims:
                self._add_tab(tr(f"veditor.typo_editor.preset_cat.{cat}"), anims)

    def _add_tab(self, label: str, presets: list) -> None:
        from PySide6.QtWidgets import QScrollArea, QGridLayout

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)
        scroll.setWidget(grid_host)

        cols = 3
        for idx, preset in enumerate(presets):
            tile = self._make_tile(preset)
            grid.addWidget(tile, idx // cols, idx % cols)
            self._tile_buttons.append(tile)
        grid.setRowStretch(grid.rowCount(), 1)
        self._tabs.addTab(page, label)

    def _make_tile(self, preset) -> QWidget:
        tile = QPushButton()
        # Search payload: name + reference + id
        tile.setProperty("preset_id", preset.id)
        search_blob = f"{tr(preset.name_key)} {preset.reference_artist} {preset.id}"
        tile.setProperty("preset_search", search_blob)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setMinimumSize(150, 92)
        tile.setMaximumHeight(110)
        tile.setStyleSheet(
            f"QPushButton {{ "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 2px solid {COLOR_BORDER_DEFAULT}; border-radius: 6px; "
            f"padding: 6px; text-align: left; }}"
            f"QPushButton:hover {{ border-color: #6a3cb5; "
            f"background-color: #34343c; }}"
        )

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Top: icon + name on one line
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        icon = QLabel(preset.icon)
        icon.setStyleSheet("font-size: 22px; background: transparent; border: none;")
        top.addWidget(icon)
        name = QLabel(tr(preset.name_key))
        name.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; font-weight: 700; "
            f"background: transparent; border: none;"
        )
        name.setWordWrap(True)
        top.addWidget(name, 1)
        layout.addLayout(top)

        # Bottom: reference artist (if any)
        if preset.reference_artist:
            ref = QLabel(f"— {preset.reference_artist}")
            ref.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
                f"background: transparent; border: none;"
            )
            layout.addWidget(ref)

        layout.addStretch(1)
        tile.clicked.connect(lambda _c=False, pid=preset.id: self._select(pid))
        return tile

    def _select(self, preset_id: str) -> None:
        if self._popup is not None:
            self._popup.hide()
        self.preset_applied.emit(preset_id)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        for tile in self._tile_buttons:
            haystack = (tile.property("preset_search") or "").lower()
            tile.setVisible(not needle or needle in haystack)


class TypographyEditorDialog(QDialog):
    """Phase 2 typography editor — 3-pane (text / animation placeholder
    / style) modal with a real-time preview at the top.

    Edits mutate the clip in-place so the underlying preview updates
    live; Cancel restores from a snapshot taken at open time."""

    WEIGHT_PRESETS = [
        ("thin", 200),
        ("regular", 400),
        ("bold", 700),
        ("black", 900),
    ]

    ALIGN_OPTIONS = ("left", "center", "right")

    def __init__(self, clip: TextClip, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip = clip
        self._snapshot = self._snapshot_clip()
        self._suppress_signals = False

        # Capture the parent editor's current preview frame for the
        # video-background option. Copy so subsequent player frames
        # don't mutate it under us.
        self._video_bg_pixmap: QPixmap | None = None
        if parent is not None:
            pm = getattr(parent, "_preview_pixmap", None)
            if pm is not None and not pm.isNull():
                self._video_bg_pixmap = QPixmap(pm)
        self._show_video_bg: bool = self._video_bg_pixmap is not None

        title = clip.text[:30] or "—"
        self.setWindowTitle(tr("veditor.typo_editor.title", name=title))
        self.setModal(True)
        self.resize(1200, 800)
        self.setStyleSheet(
            f"QDialog {{ background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; }}"
            f"QLabel {{ color: {COLOR_TEXT_SECONDARY}; }}"
            f"QGroupBox {{ color: {COLOR_TEXT_PRIMARY}; font-weight: 700; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"margin-top: 10px; padding-top: 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; "
            f"subcontrol-position: top left; left: 10px; padding: 0 4px; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # ---- Preview ----
        self._preview_view = _PreviewView()
        self._preview_view.setMinimumHeight(280)
        self._preview_item = _TextPreviewItem(
            clip,
            bg_provider=self._current_bg,
            time_provider=self._current_play_time,
        )
        self._preview_view.add_item(self._preview_item.graphics_item())
        root.addWidget(self._preview_view, stretch=2)

        # Playback state for animation preview.
        self._play_time_s: float = 0.0
        self._is_playing: bool = False
        from PySide6.QtCore import QTimer
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(33)         # ~30 fps; smooth enough
        self._play_timer.timeout.connect(self._on_play_tick)

        # Preview controls row: Play / Reset + Video-background toggle
        from PySide6.QtWidgets import QCheckBox
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(6)

        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("ToolButton")
        self._play_btn.setFixedWidth(40)
        self._play_btn.setToolTip(tr("veditor.typo_editor.preview_play"))
        self._play_btn.clicked.connect(self._toggle_preview_play)
        ctrl_row.addWidget(self._play_btn)

        self._reset_btn = QPushButton("⟲")
        self._reset_btn.setObjectName("ToolButton")
        self._reset_btn.setFixedWidth(40)
        self._reset_btn.setToolTip(tr("veditor.typo_editor.preview_reset"))
        self._reset_btn.clicked.connect(self._reset_preview)
        ctrl_row.addWidget(self._reset_btn)

        self._play_label = QLabel(self._format_play_label())
        self._play_label.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"font-family: Consolas, monospace;"
        )
        ctrl_row.addWidget(self._play_label)

        ctrl_row.addStretch(1)

        self._video_bg_check = QCheckBox(tr("veditor.typo_editor.show_video_bg"))
        self._video_bg_check.setChecked(self._show_video_bg)
        self._video_bg_check.setEnabled(self._video_bg_pixmap is not None)
        if self._video_bg_pixmap is None:
            self._video_bg_check.setToolTip(
                tr("veditor.typo_editor.show_video_bg.unavailable")
            )
        self._video_bg_check.toggled.connect(self._on_video_bg_toggle)
        ctrl_row.addWidget(self._video_bg_check)

        root.addLayout(ctrl_row)

        # ---- Preset picker (single full-width purple button) ----
        self._preset_picker = _PresetPickerButton()
        self._preset_picker.preset_applied.connect(self._on_preset_picked)
        root.addWidget(self._preset_picker)

        # ---- 3 panes ----
        panes = QHBoxLayout()
        panes.setSpacing(10)
        panes.addWidget(self._build_text_pane(), stretch=1)
        panes.addWidget(self._build_animation_pane(), stretch=1)
        panes.addWidget(self._build_style_pane(), stretch=2)
        self._panes_layout = panes        # kept for preset-apply rebuild
        root.addLayout(panes, stretch=3)

        # ---- Buttons ----
        from PySide6.QtWidgets import QDialogButtonBox
        bb = QDialogButtonBox()
        save_btn = bb.addButton(
            tr("veditor.typo_editor.save_template"),
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        save_btn.setEnabled(False)  # Phase 4: preset system
        save_btn.setToolTip(tr("veditor.typo_editor.save_template.tooltip"))
        cancel_btn = bb.addButton(
            tr("veditor.typo_editor.cancel"),
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        apply_btn = bb.addButton(
            tr("veditor.typo_editor.apply"),
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        apply_btn.setDefault(True)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self._on_cancel)
        root.addWidget(bb)

    # ---- snapshot / cancel ----

    def _snapshot_clip(self) -> dict:
        import copy
        return {
            "text": self._clip.text,
            "style": copy.deepcopy(self._clip.style),
            "in_duration": self._clip.animation.in_duration,
            "out_duration": self._clip.animation.out_duration,
            "in_animation": self._clip.animation.in_animation,
            "out_animation": self._clip.animation.out_animation,
            "hold_animation": getattr(self._clip.animation, "hold_animation", "none"),
            "in_extras": list(getattr(self._clip.animation, "in_extras", []) or []),
            "out_extras": list(getattr(self._clip.animation, "out_extras", []) or []),
            "hold_extras": list(getattr(self._clip.animation, "hold_extras", []) or []),
            "in_intensity": self._clip.animation.in_intensity,
            "out_intensity": self._clip.animation.out_intensity,
            "hold_intensity": getattr(self._clip.animation, "hold_intensity", 100.0),
            "mono_color": getattr(self._clip.animation, "mono_color", False),
        }

    def _on_cancel(self) -> None:
        snap = self._snapshot
        self._clip.text = snap["text"]
        self._clip.style = snap["style"]
        self._clip.animation.in_duration = snap["in_duration"]
        self._clip.animation.out_duration = snap["out_duration"]
        self._clip.animation.in_animation = snap["in_animation"]
        self._clip.animation.out_animation = snap["out_animation"]
        self._clip.animation.hold_animation = snap["hold_animation"]
        self._clip.animation.in_extras = list(snap["in_extras"])
        self._clip.animation.out_extras = list(snap["out_extras"])
        self._clip.animation.hold_extras = list(snap["hold_extras"])
        self._clip.animation.in_intensity = snap["in_intensity"]
        self._clip.animation.out_intensity = snap["out_intensity"]
        self._clip.animation.hold_intensity = snap["hold_intensity"]
        self._clip.animation.mono_color = snap["mono_color"]
        self.reject()

    def closeEvent(self, event) -> None:
        if hasattr(self, "_play_timer"):
            self._play_timer.stop()
        super().closeEvent(event)

    def _refresh_preview(self) -> None:
        self._preview_item.refresh()

    def _current_bg(self):
        """Provider used by ``_TextPreviewItem`` — returns the captured
        video frame when the user wants it shown, else ``None`` for a
        plain black backdrop."""
        if self._show_video_bg and self._video_bg_pixmap is not None:
            return self._video_bg_pixmap
        return None

    def _on_video_bg_toggle(self, on: bool) -> None:
        self._show_video_bg = bool(on)
        self._refresh_preview()

    # ---- preview playback ----

    def _current_play_time(self):
        """Animation time provider. Returns seconds-since-clip-start
        when the user is actively playing; ``None`` while paused (so
        the preview shows the steady HOLD state for editing)."""
        if self._is_playing:
            return self._play_time_s
        # When paused, show the steady "fully on screen" state by
        # passing a time that lands inside HOLD.
        return None

    def _toggle_preview_play(self) -> None:
        if self._is_playing:
            self._is_playing = False
            self._play_timer.stop()
            self._play_btn.setText("▶")
        else:
            # Start fresh from 0 if we were paused at end.
            if self._play_time_s >= self._clip.duration_s - 0.001:
                self._play_time_s = 0.0
            self._is_playing = True
            self._play_timer.start()
            self._play_btn.setText("⏸")
        self._refresh_preview()
        self._update_play_label()

    def _reset_preview(self) -> None:
        self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _on_play_tick(self) -> None:
        # Advance and loop. Looping makes it easy to compare animations
        # without mashing the play button between every change.
        self._play_time_s += self._play_timer.interval() / 1000.0
        if self._play_time_s >= self._clip.duration_s:
            self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _format_play_label(self) -> str:
        return f"{self._play_time_s:5.2f} / {self._clip.duration_s:5.2f} s"

    def _update_play_label(self) -> None:
        if hasattr(self, "_play_label"):
            self._play_label.setText(self._format_play_label())

    # ---- text pane ----

    def _build_text_pane(self) -> QWidget:
        from PySide6.QtWidgets import QGroupBox, QPlainTextEdit

        box = QGroupBox(tr("veditor.typo_editor.text_pane"))
        box.setMinimumWidth(220)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(8)

        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlainText(self._clip.text)
        self._text_edit.setPlaceholderText(tr("veditor.typo_editor.placeholder"))
        self._text_edit.setStyleSheet(
            f"QPlainTextEdit {{ padding: 8px; font-size: 14px; "
            f"background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; }}"
        )
        self._text_edit.textChanged.connect(self._on_text_changed)
        lay.addWidget(self._text_edit, stretch=1)

        return box

    def _on_text_changed(self) -> None:
        if self._suppress_signals:
            return
        self._clip.text = self._text_edit.toPlainText()
        self._refresh_preview()

    # ---- animation pane (placeholder + timing sliders) ----

    def _build_animation_pane(self) -> QWidget:
        from PySide6.QtWidgets import QGroupBox

        box = QGroupBox(tr("veditor.typo_editor.animation_pane"))
        box.setMinimumWidth(240)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(10)

        # IN animation picker — visual grid in popup.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_in")))
        self._in_picker = _AnimationPickerButton(
            self._clip.animation.in_animation, direction="in",
        )
        self._in_picker.animation_changed.connect(self._on_in_anim_picked)
        lay.addWidget(self._in_picker)
        # IN extras chip row + add button
        self._in_extras_row = self._build_extras_row("in")
        lay.addWidget(self._in_extras_row)

        # IN duration slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.timing.in"),
            value=int(self._clip.animation.in_duration * 1000),
            minimum=0, maximum=5000, suffix=" ms", step=50,
            on_change=self._on_in_changed,
        ))
        # IN intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.in"),
            value=int(self._clip.animation.in_intensity),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_in_intensity_changed,
        ))

        # OUT animation picker
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_out")))
        self._out_picker = _AnimationPickerButton(
            self._clip.animation.out_animation, direction="out",
        )
        self._out_picker.animation_changed.connect(self._on_out_anim_picked)
        lay.addWidget(self._out_picker)
        # OUT extras chip row
        self._out_extras_row = self._build_extras_row("out")
        lay.addWidget(self._out_extras_row)

        # OUT duration slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.timing.out"),
            value=int(self._clip.animation.out_duration * 1000),
            minimum=0, maximum=5000, suffix=" ms", step=50,
            on_change=self._on_out_changed,
        ))
        # OUT intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.out"),
            value=int(self._clip.animation.out_intensity),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_out_intensity_changed,
        ))

        # HOLD animation picker — loops between IN and OUT.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.anim_hold")))
        self._hold_picker = _AnimationPickerButton(
            getattr(self._clip.animation, "hold_animation", "none"),
            direction="hold",
        )
        self._hold_picker.animation_changed.connect(self._on_hold_anim_picked)
        lay.addWidget(self._hold_picker)
        # HOLD extras chip row
        self._hold_extras_row = self._build_extras_row("hold")
        lay.addWidget(self._hold_extras_row)

        # HOLD intensity slider
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.intensity.hold"),
            value=int(getattr(self._clip.animation, "hold_intensity", 100.0)),
            minimum=0, maximum=200, suffix=" %", step=5,
            on_change=self._on_hold_intensity_changed,
        ))

        # Hold derived label (live) — shows the seconds available between IN and OUT.
        self._hold_label = QLabel("")
        self._hold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hold_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")
        self._update_hold_label()
        lay.addWidget(self._hold_label)

        # Mono-color toggle — disables per-glyph color overrides
        # (e.g. Angle Break's flash) so the whole clip stays one tone.
        from PySide6.QtWidgets import QCheckBox
        self._mono_check = QCheckBox(tr("veditor.typo_editor.mono_color"))
        self._mono_check.setChecked(bool(getattr(self._clip.animation, "mono_color", False)))
        self._mono_check.setToolTip(tr("veditor.typo_editor.mono_color.tooltip"))
        self._mono_check.toggled.connect(self._on_mono_color_toggle)
        lay.addWidget(self._mono_check)

        lay.addStretch(1)
        return box

    # ---- extras (composed animations) ----

    def _extras_attr(self, direction: str) -> str:
        return f"{direction}_extras"

    def _build_extras_row(self, direction: str) -> QWidget:
        """Wraps the chips + an `[+ Add modifier]` button for one slot.
        The wrapper widget keeps a hidden ``_AnimationPickerButton`` in
        ``extras_mode`` so we get the picker popup for free."""
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # Hidden adder picker: we trigger its popup by clicking the
        # visible add-button. Adding it to the layout keeps Qt's parent
        # ownership tidy; visibility is the picker button's responsibility.
        adder = _AnimationPickerButton(
            current_id="none", direction=direction, extras_mode=True,
        )
        adder.animation_changed.connect(
            lambda aid, d=direction: self._on_extra_added(d, aid)
        )
        setattr(self, f"_{direction}_adder", adder)

        chips_host = QWidget()
        chips_lay = QHBoxLayout(chips_host)
        chips_lay.setContentsMargins(0, 0, 0, 0)
        chips_lay.setSpacing(4)
        setattr(self, f"_{direction}_chips_lay", chips_lay)

        lay.addWidget(chips_host, 0)
        lay.addWidget(adder, 1)
        self._render_extras_chips(direction)
        return wrap

    def _render_extras_chips(self, direction: str) -> None:
        """Rebuild the chip widgets for ``direction`` from the current
        clip state."""
        chips_lay: QHBoxLayout | None = getattr(self, f"_{direction}_chips_lay", None)
        if chips_lay is None:
            return
        # Clear existing
        while chips_lay.count():
            item = chips_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        extras = list(getattr(self._clip.animation, self._extras_attr(direction), []) or [])
        from app.typo_animations import get_animation
        for idx, aid in enumerate(extras):
            anim = get_animation(aid)
            chip = QPushButton(f" {anim.icon} {tr(anim.name_key)}  ✕")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip(tr("veditor.typo_editor.modifier.remove_tooltip"))
            chip.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; "
                f"color: {COLOR_TEXT_PRIMARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
                f"border-radius: 10px; padding: 2px 8px; font-size: 10px; }}"
                f"QPushButton:hover {{ background-color: #4a3a3a; "
                f"border-color: #7a4a4a; }}"
            )
            chip.clicked.connect(
                lambda _c=False, d=direction, i=idx: self._on_extra_removed(d, i)
            )
            chips_lay.addWidget(chip)

    def _on_extra_added(self, direction: str, anim_id: str) -> None:
        if not anim_id or anim_id == "none":
            return
        attr = self._extras_attr(direction)
        cur = list(getattr(self._clip.animation, attr, []) or [])
        cur.append(anim_id)
        setattr(self._clip.animation, attr, cur)
        self._render_extras_chips(direction)
        self._refresh_preview()

    def _on_extra_removed(self, direction: str, index: int) -> None:
        attr = self._extras_attr(direction)
        cur = list(getattr(self._clip.animation, attr, []) or [])
        if 0 <= index < len(cur):
            del cur[index]
            setattr(self._clip.animation, attr, cur)
            self._render_extras_chips(direction)
            self._refresh_preview()

    # ---- primary picker handlers ----

    def _on_in_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.in_animation = anim_id
        self._refresh_preview()

    def _on_out_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.out_animation = anim_id
        self._refresh_preview()

    def _on_hold_anim_picked(self, anim_id: str) -> None:
        self._clip.animation.hold_animation = anim_id
        self._refresh_preview()

    def _on_preset_picked(self, preset_id: str) -> None:
        """Apply a preset bundle to the clip and rebuild the editor's
        controls so users immediately see the new animation + style
        choices. Animation pane (pickers + sliders) and style pane
        (font, size, weight, effects, etc.) need a full rebuild — the
        cheapest way is to discard them and re-add."""
        from app.typo_presets import get_preset, apply_preset
        preset = get_preset(preset_id)
        if preset is None:
            return
        apply_preset(self._clip, preset)

        # Rebuild the IN/OUT pickers' visible label by re-syncing them
        # to the clip's new animation ids.
        self._in_picker.set_current(self._clip.animation.in_animation)
        self._out_picker.set_current(self._clip.animation.out_animation)
        if hasattr(self, "_hold_picker"):
            self._hold_picker.set_current(
                getattr(self._clip.animation, "hold_animation", "none"),
            )

        # The size / weight / color / sliders / effects don't have a
        # cheap "set value" path that handles every control, so the
        # safest move is to rebuild the whole 3-pane row. Delegate to a
        # helper that swaps the panes in place.
        self._rebuild_panes()

        # Reset the preview clock so the user sees the IN sequence of
        # the new preset right away.
        self._play_time_s = 0.0
        self._refresh_preview()
        self._update_play_label()

    def _rebuild_panes(self) -> None:
        """Replace the 3-pane row with freshly-built widgets so every
        control reflects current clip state. Called after preset apply."""
        panes_layout = self._panes_layout
        if panes_layout is None:
            return
        # Remove old widgets
        while panes_layout.count():
            item = panes_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        panes_layout.addWidget(self._build_text_pane(), stretch=1)
        panes_layout.addWidget(self._build_animation_pane(), stretch=1)
        panes_layout.addWidget(self._build_style_pane(), stretch=2)

    def _slider_row(self, *, label: str, value: int, minimum: int,
                    maximum: int, suffix: str, step: int, on_change) -> QWidget:
        """Inline label + QSlider + value-readout helper."""
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")
        readout = QLabel(f"{value}{suffix}")
        readout.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600;")
        readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(lbl)
        head.addStretch(1)
        head.addWidget(readout)
        v.addLayout(head)

        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(minimum, maximum)
        sld.setSingleStep(step)
        sld.setPageStep(step * 4)
        sld.setValue(int(value))

        def _emit(val: int) -> None:
            readout.setText(f"{val}{suffix}")
            on_change(val)

        sld.valueChanged.connect(_emit)
        v.addWidget(sld)
        return wrap

    def _on_in_changed(self, ms: int) -> None:
        self._clip.animation.in_duration = max(0.0, ms / 1000.0)
        self._update_hold_label()
        self._refresh_preview()

    def _on_out_changed(self, ms: int) -> None:
        self._clip.animation.out_duration = max(0.0, ms / 1000.0)
        self._update_hold_label()
        self._refresh_preview()

    def _on_in_intensity_changed(self, percent: int) -> None:
        self._clip.animation.in_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_out_intensity_changed(self, percent: int) -> None:
        self._clip.animation.out_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_hold_intensity_changed(self, percent: int) -> None:
        self._clip.animation.hold_intensity = max(0.0, min(200.0, float(percent)))
        self._refresh_preview()

    def _on_mono_color_toggle(self, on: bool) -> None:
        self._clip.animation.mono_color = bool(on)
        self._refresh_preview()

    def _update_hold_label(self) -> None:
        if not hasattr(self, "_hold_label"):
            return
        hold = self._clip.hold_duration_s
        self._hold_label.setText(
            tr("veditor.typo_editor.timing.hold", seconds=f"{hold:.2f}")
        )

    # ---- style pane ----

    # Recommended fonts pinned to the top of the picker. These are the
    # families the typography spec recommends for Korean / Japanese MV
    # styles + a few staple Latin display faces. Filtered against the
    # actual installed set at runtime.
    PINNED_FONTS = (
        "Pretendard",
        "Noto Sans KR",
        "Noto Serif KR",
        "Nanum Myeongjo",
        "Gaegu",
        "Noto Sans JP",
        "Noto Serif JP",
        "Shippori Mincho",
        "Arial",
        "Segoe UI",
        "Impact",
    )

    def _build_style_pane(self) -> QWidget:
        from PySide6.QtWidgets import (
            QGroupBox, QPushButton, QButtonGroup, QSpinBox,
        )

        box = QGroupBox(tr("veditor.typo_editor.style_pane"))
        box.setMinimumWidth(300)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(10)

        s = self._clip.style

        # Font family — compact button + click-to-open popup picker.
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.font")))
        self._font_picker = _FontPickerButton(s.font_family)
        self._font_picker.font_changed.connect(self._on_font_family_changed)
        lay.addWidget(self._font_picker)

        # Size
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.size")))
        size_row = QHBoxLayout()
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(16, 200)
        self._size_slider.setValue(int(s.font_size))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(16, 200)
        self._size_spin.setValue(int(s.font_size))
        self._size_spin.setFixedWidth(64)
        self._size_slider.valueChanged.connect(self._size_spin.setValue)
        self._size_spin.valueChanged.connect(self._size_slider.setValue)
        self._size_spin.valueChanged.connect(self._on_size_changed)
        size_row.addWidget(self._size_slider, stretch=1)
        size_row.addWidget(self._size_spin)
        lay.addLayout(size_row)

        # Weight buttons
        lay.addWidget(self._labelled(tr("veditor.typo_editor.style.weight")))
        weight_row = QHBoxLayout()
        self._weight_group = QButtonGroup(self)
        self._weight_group.setExclusive(True)
        for key, weight in self.WEIGHT_PRESETS:
            btn = QPushButton(tr(f"veditor.typo_editor.weight.{key}"))
            btn.setObjectName("ToolButton")
            btn.setCheckable(True)
            btn.setProperty("weight", weight)
            if abs(s.font_weight - weight) < 50:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c=False, w=weight: self._on_weight_changed(w))
            self._weight_group.addButton(btn)
            weight_row.addWidget(btn)
        lay.addLayout(weight_row)

        # Color + Alignment row
        ca_row = QHBoxLayout()
        self._color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._color_btn.setObjectName("ToolButton")
        self._update_color_btn_swatch()
        self._color_btn.clicked.connect(self._on_color_picked)
        ca_row.addWidget(self._color_btn, stretch=1)

        # Alignment
        self._align_group = QButtonGroup(self)
        self._align_group.setExclusive(True)
        for key in self.ALIGN_OPTIONS:
            btn = QPushButton(tr(f"veditor.typo_editor.align.{key}"))
            btn.setObjectName("ToolButton")
            btn.setCheckable(True)
            btn.setProperty("align_key", key)
            if s.alignment == key:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c=False, k=key: self._on_align_changed(k))
            self._align_group.addButton(btn)
            ca_row.addWidget(btn)
        lay.addLayout(ca_row)

        # Position X / Y
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.position_x"),
            value=int(s.position_x * 100),
            minimum=0, maximum=100, suffix=" %", step=1,
            on_change=self._on_pos_x_changed,
        ))
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.position_y"),
            value=int(s.position_y * 100),
            minimum=0, maximum=100, suffix=" %", step=1,
            on_change=self._on_pos_y_changed,
        ))

        # Letter spacing
        lay.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.style.letter_spacing"),
            value=int(s.letter_spacing),
            minimum=-5, maximum=30, suffix=" px", step=1,
            on_change=self._on_letter_spacing_changed,
        ))

        # Effects (outline / shadow / background) — collapsed-style block
        lay.addWidget(self._build_effects_block())

        lay.addStretch(1)
        return box

    def _build_effects_block(self) -> QWidget:
        from PySide6.QtWidgets import QCheckBox, QGroupBox, QPushButton

        s = self._clip.style
        box = QGroupBox(tr("veditor.typo_editor.effects.section"))
        v = QVBoxLayout(box)
        v.setContentsMargins(8, 14, 8, 8)
        v.setSpacing(6)

        # ---- Outline ----
        ol_row = QHBoxLayout()
        self._outline_check = QCheckBox(tr("veditor.typo_editor.effects.outline"))
        self._outline_check.setChecked(bool(s.outline_color and s.outline_width > 0))
        self._outline_check.toggled.connect(self._on_outline_toggle)
        ol_row.addWidget(self._outline_check)
        self._outline_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._outline_color_btn.setObjectName("ToolButton")
        self._update_outline_swatch()
        self._outline_color_btn.clicked.connect(self._on_outline_color)
        ol_row.addWidget(self._outline_color_btn)
        v.addLayout(ol_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.outline_width"),
            value=int(s.outline_width or 0),
            minimum=0, maximum=12, suffix=" px", step=1,
            on_change=self._on_outline_width,
        ))

        # ---- Shadow ----
        sh_row = QHBoxLayout()
        self._shadow_check = QCheckBox(tr("veditor.typo_editor.effects.shadow"))
        self._shadow_check.setChecked(bool(s.shadow_color))
        self._shadow_check.toggled.connect(self._on_shadow_toggle)
        sh_row.addWidget(self._shadow_check)
        self._shadow_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._shadow_color_btn.setObjectName("ToolButton")
        self._update_shadow_swatch()
        self._shadow_color_btn.clicked.connect(self._on_shadow_color)
        sh_row.addWidget(self._shadow_color_btn)
        v.addLayout(sh_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.shadow_x"),
            value=int(s.shadow_offset_x or 0),
            minimum=-20, maximum=20, suffix=" px", step=1,
            on_change=self._on_shadow_x,
        ))
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.shadow_y"),
            value=int(s.shadow_offset_y or 0),
            minimum=-20, maximum=20, suffix=" px", step=1,
            on_change=self._on_shadow_y,
        ))

        # ---- Background ----
        bg_row = QHBoxLayout()
        self._bg_check = QCheckBox(tr("veditor.typo_editor.effects.background"))
        self._bg_check.setChecked(bool(s.background_color))
        self._bg_check.toggled.connect(self._on_bg_toggle)
        bg_row.addWidget(self._bg_check)
        self._bg_color_btn = QPushButton(tr("veditor.typo_editor.btn.color"))
        self._bg_color_btn.setObjectName("ToolButton")
        self._update_bg_swatch()
        self._bg_color_btn.clicked.connect(self._on_bg_color)
        bg_row.addWidget(self._bg_color_btn)
        v.addLayout(bg_row)
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.bg_padding"),
            value=int(s.background_padding or 0),
            minimum=0, maximum=80, suffix=" px", step=2,
            on_change=self._on_bg_padding,
        ))
        v.addWidget(self._slider_row(
            label=tr("veditor.typo_editor.effects.bg_radius"),
            value=int(s.background_radius or 0),
            minimum=0, maximum=80, suffix=" px", step=2,
            on_change=self._on_bg_radius,
        ))

        return box

    @staticmethod
    def _labelled(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
                          f"font-weight: 700; letter-spacing: 0.5px;")
        return lbl

    # ---- style change handlers ----

    def _on_font_family_changed(self, family: str) -> None:
        self._clip.style.font_family = family
        self._refresh_preview()

    def _on_size_changed(self, value: int) -> None:
        self._clip.style.font_size = int(value)
        self._refresh_preview()

    def _on_weight_changed(self, weight: int) -> None:
        self._clip.style.font_weight = int(weight)
        self._refresh_preview()

    def _on_color_picked(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.color or "#FFFFFF")
        chosen = QColorDialog.getColor(cur, self,
                                       tr("veditor.typo_editor.color_dialog"))
        if chosen.isValid():
            self._clip.style.color = chosen.name()
            self._update_color_btn_swatch()
            self._refresh_preview()

    def _on_align_changed(self, key: str) -> None:
        self._clip.style.alignment = key
        self._refresh_preview()

    def _on_pos_x_changed(self, percent: int) -> None:
        self._clip.style.position_x = max(0.0, min(1.0, percent / 100.0))
        self._refresh_preview()

    def _on_pos_y_changed(self, percent: int) -> None:
        self._clip.style.position_y = max(0.0, min(1.0, percent / 100.0))
        self._refresh_preview()

    def _on_letter_spacing_changed(self, value: int) -> None:
        self._clip.style.letter_spacing = int(value)
        self._refresh_preview()

    # ---- effects ----

    def _on_outline_toggle(self, on: bool) -> None:
        if on and not self._clip.style.outline_color:
            self._clip.style.outline_color = "#000000"
        if on and self._clip.style.outline_width <= 0:
            self._clip.style.outline_width = 2
        if not on:
            self._clip.style.outline_width = 0
        self._update_outline_swatch()
        self._refresh_preview()

    def _on_outline_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.outline_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.outline_color = c.name()
            if not self._outline_check.isChecked():
                self._outline_check.setChecked(True)
            self._update_outline_swatch()
            self._refresh_preview()

    def _on_outline_width(self, w: int) -> None:
        self._clip.style.outline_width = int(w)
        if w > 0 and not self._outline_check.isChecked():
            self._outline_check.setChecked(True)
        self._refresh_preview()

    def _on_shadow_toggle(self, on: bool) -> None:
        if on and not self._clip.style.shadow_color:
            self._clip.style.shadow_color = "#000000"
        if on and not (self._clip.style.shadow_offset_x or self._clip.style.shadow_offset_y):
            self._clip.style.shadow_offset_x = 3
            self._clip.style.shadow_offset_y = 3
        if not on:
            self._clip.style.shadow_color = None
        self._update_shadow_swatch()
        self._refresh_preview()

    def _on_shadow_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.shadow_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.shadow_color = c.name()
            if not self._shadow_check.isChecked():
                self._shadow_check.setChecked(True)
            self._update_shadow_swatch()
            self._refresh_preview()

    def _on_shadow_x(self, v: int) -> None:
        self._clip.style.shadow_offset_x = int(v)
        self._refresh_preview()

    def _on_shadow_y(self, v: int) -> None:
        self._clip.style.shadow_offset_y = int(v)
        self._refresh_preview()

    def _on_bg_toggle(self, on: bool) -> None:
        if on and not self._clip.style.background_color:
            self._clip.style.background_color = "#000000"
        if not on:
            self._clip.style.background_color = None
        self._update_bg_swatch()
        self._refresh_preview()

    def _on_bg_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._clip.style.background_color or "#000000")
        c = QColorDialog.getColor(cur, self, tr("veditor.typo_editor.color_dialog"))
        if c.isValid():
            self._clip.style.background_color = c.name()
            if not self._bg_check.isChecked():
                self._bg_check.setChecked(True)
            self._update_bg_swatch()
            self._refresh_preview()

    def _on_bg_padding(self, v: int) -> None:
        self._clip.style.background_padding = int(v)
        self._refresh_preview()

    def _on_bg_radius(self, v: int) -> None:
        self._clip.style.background_radius = int(v)
        self._refresh_preview()

    # ---- swatch updates ----

    def _swatch_style(self, hex_color: str | None) -> str:
        c = hex_color or "transparent"
        return (
            f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 8px; text-align: left; }}"
            # We'll prepend a colored square via icon-ish trick below
        )

    def _set_swatch_button(self, btn, hex_color: str | None, label: str) -> None:
        c = hex_color or "transparent"
        if hex_color:
            btn.setText(f"  {label}  ({hex_color})")
            # Use a stylesheet block with a left-side colored gutter
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_PRIMARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; padding: 4px 8px; "
                f"border-left: 12px solid {hex_color}; }}"
                f"QPushButton:hover {{ border-color: #6a6a72; }}"
            )
        else:
            btn.setText(f"  {label}")
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {COLOR_BG_L4}; color: {COLOR_TEXT_TERTIARY}; "
                f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; padding: 4px 8px; }}"
                f"QPushButton:hover {{ border-color: #6a6a72; }}"
            )

    def _update_color_btn_swatch(self) -> None:
        self._set_swatch_button(
            self._color_btn, self._clip.style.color,
            tr("veditor.typo_editor.btn.text_color"),
        )

    def _update_outline_swatch(self) -> None:
        col = self._clip.style.outline_color if self._clip.style.outline_width else None
        self._set_swatch_button(
            self._outline_color_btn, col,
            tr("veditor.typo_editor.btn.color"),
        )

    def _update_shadow_swatch(self) -> None:
        self._set_swatch_button(
            self._shadow_color_btn, self._clip.style.shadow_color,
            tr("veditor.typo_editor.btn.color"),
        )

    def _update_bg_swatch(self) -> None:
        self._set_swatch_button(
            self._bg_color_btn, self._clip.style.background_color,
            tr("veditor.typo_editor.btn.color"),
        )


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
            /* AI Master tab uses the orange accent so users can see
               at a glance which tab drives the post-processing chain. */
            QPushButton#SETabAI {{
                background: transparent;
                color: #D85A30;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 18px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton#SETabAI:hover {{ color: #ff7a4a; }}
            QPushButton#SETabAI:checked {{
                color: #ff7a4a;
                border-bottom: 2px solid #D85A30;
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
            /* AI Master preset tiles: bigger, 3x2 grid, orange accent. */
            QPushButton#SEAIPresetBtn {{
                background-color: rgba(216, 90, 48, 0.08);
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid rgba(216, 90, 48, 0.35);
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton#SEAIPresetBtn:hover {{
                background-color: rgba(216, 90, 48, 0.18);
                color: #ff7a4a;
                border-color: #D85A30;
            }}
            QPushButton#SEAIPresetBtn[selected="true"] {{
                background-color: rgba(216, 90, 48, 0.25);
                color: #fff;
                border-color: #D85A30;
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
            ("ai_master", tr("veditor.sound_editor.tab.ai_master")),
        ]
        self._tab_buttons: dict[str, QPushButton] = {}
        for tab_id, tab_label in tabs:
            # "AI Master" gets an orange accent + "NEW" badge appended
            # via HTML — QPushButton supports rich text through a
            # QTextDocument paint path. Simplest trick: append NEW as
            # a unicode suffix styled via QSS descendant selectors.
            if tab_id == "ai_master":
                btn = QPushButton(f"{tab_label}  NEW")
                btn.setObjectName("SETabAI")
            else:
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
        self._tab_stack.addWidget(self._build_basic_tab())      # 0
        self._tab_stack.addWidget(self._build_eq_tab())          # 1
        self._tab_stack.addWidget(self._build_dynamics_tab())    # 2
        self._tab_stack.addWidget(self._build_effects_tab())     # 3
        self._tab_stack.addWidget(self._build_advanced_tab())    # 4
        self._tab_stack.addWidget(self._build_ai_master_tab())   # 5
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

    # ========= EQ tab =========

    EQ_PRESETS: dict[str, dict] = {
        "Flat":        {"low_g": 0, "mid_g": 0, "high_g": 0},
        "Vocal Boost": {"low_g": -2, "mid_g": 4, "high_g": 2},
        "Bass Boost":  {"low_g": 6, "mid_g": 0, "high_g": 0},
        "Podcast":     {"low_g": -3, "mid_g": 2, "high_g": 3},
        "Treble Cut":  {"low_g": 0, "mid_g": 0, "high_g": -4},
    }

    def _build_eq_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget, fmt_db, fmt_hz
        eq = self.clip.effects["eq"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # Enable toggle at top
        self._eq_enabled_btn = QPushButton(tr("veditor.sound_editor.fx.enabled"))
        self._eq_enabled_btn.setObjectName("SEActionBtn")
        self._eq_enabled_btn.setCheckable(True)
        self._eq_enabled_btn.setChecked(bool(eq.get("enabled")))
        self._eq_enabled_btn.toggled.connect(lambda on: self._set_fx("eq", "enabled", on))
        row_top = QHBoxLayout()
        row_top.addWidget(self._eq_enabled_btn)
        row_top.addStretch(1)
        root.addLayout(row_top)

        # Curve visualization
        self._eq_curve = _EqCurveView(self.clip)
        self._eq_curve.setFixedHeight(88)
        root.addWidget(self._eq_curve)

        # 3 band rows (each with Freq / Gain / Q)
        def _band_ui(band: str, freq_range: tuple[float, float]) -> QHBoxLayout:
            band_state = eq[band]
            row = QHBoxLayout()
            row.setSpacing(10)
            lbl = QLabel(band.upper())
            lbl.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; "
                f"font-weight: 700; letter-spacing: 2px; min-width: 50px;"
            )
            row.addWidget(lbl)

            k_freq = KnobWidget(
                label="Freq", value=band_state["freq"],
                minimum=freq_range[0], maximum=freq_range[1],
                default=band_state["freq"],
                color="blue", logarithmic=True, formatter=fmt_hz,
            )
            k_gain = KnobWidget(
                label="Gain", value=band_state["gain"],
                minimum=-12, maximum=12, default=0,
                color="green", bipolar=True, formatter=fmt_db,
            )
            k_q = KnobWidget(
                label="Q", value=band_state["q"],
                minimum=0.1, maximum=10, default=band_state["q"],
                color="orange",
                formatter=lambda v: f"{v:.2f}",
            )
            k_freq.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "freq"), v))
            k_gain.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "gain"), v))
            k_q.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "q"), v))
            row.addWidget(k_freq)
            row.addWidget(k_gain)
            row.addWidget(k_q)
            row.addStretch(1)
            return row

        root.addLayout(_band_ui("low", (20, 250)))
        root.addLayout(_band_ui("mid", (200, 5000)))
        root.addLayout(_band_ui("high", (2000, 20000)))

        # Presets
        root.addLayout(self._preset_row(
            self.EQ_PRESETS.keys(),
            lambda name: self._apply_eq_preset(name),
        ))
        root.addStretch(1)
        return panel

    def _apply_eq_preset(self, name: str) -> None:
        p = self.EQ_PRESETS.get(name) or {}
        eq = self.clip.effects["eq"]
        eq["low"]["gain"]  = p.get("low_g", 0)
        eq["mid"]["gain"]  = p.get("mid_g", 0)
        eq["high"]["gain"] = p.get("high_g", 0)
        eq["enabled"] = True
        self._eq_enabled_btn.setChecked(True)
        self._eq_curve.refresh()
        self._rebuild_tab_ui()

    # ========= Dynamics tab =========

    DYN_PRESETS: dict[str, dict] = {
        "Voice Gentle": {"thr": -20, "ratio": 3, "atk": 5, "rel": 120, "makeup": 2, "knee": 4},
        "Voice Strong": {"thr": -24, "ratio": 6, "atk": 2, "rel": 80,  "makeup": 4, "knee": 2},
        "Podcast":      {"thr": -18, "ratio": 4, "atk": 5, "rel": 150, "makeup": 3, "knee": 3},
    }

    def _build_dynamics_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget, fmt_db
        comp = self.clip.effects["comp"]
        gate = self.clip.effects["gate"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # --- Compressor ---
        comp_header = self._fx_header(
            tr("veditor.sound_editor.dyn.compressor"),
            "comp",
        )
        self._comp_enabled_btn = comp_header[1]
        root.addWidget(comp_header[0])

        comp_row = QHBoxLayout()
        comp_row.setSpacing(10)

        k_thr = KnobWidget(
            label="Threshold", value=comp["threshold"], minimum=-60, maximum=0,
            default=-20, unit=" dB", color="blue", formatter=fmt_db,
        )
        k_ratio = KnobWidget(
            label="Ratio", value=comp["ratio"], minimum=1, maximum=20,
            default=4, color="orange", formatter=lambda v: f"{v:.1f}:1",
        )
        k_atk = KnobWidget(
            label="Attack", value=comp["attack_ms"], minimum=0.1, maximum=100,
            default=5, color="green", logarithmic=True, formatter=lambda v: f"{v:.1f} ms",
        )
        k_rel = KnobWidget(
            label="Release", value=comp["release_ms"], minimum=10, maximum=1000,
            default=150, color="green", logarithmic=True, formatter=lambda v: f"{v:.0f} ms",
        )
        k_makeup = KnobWidget(
            label="Makeup", value=comp["makeup_db"], minimum=0, maximum=24,
            default=0, unit=" dB", color="blue", formatter=fmt_db,
        )
        k_knee = KnobWidget(
            label="Knee", value=comp["knee_db"], minimum=0, maximum=10,
            default=2, color="orange", formatter=lambda v: f"{v:.1f} dB",
        )
        k_thr.valueChanged.connect(lambda v: self._set_fx("comp", "threshold", v))
        k_ratio.valueChanged.connect(lambda v: self._set_fx("comp", "ratio", v))
        k_atk.valueChanged.connect(lambda v: self._set_fx("comp", "attack_ms", v))
        k_rel.valueChanged.connect(lambda v: self._set_fx("comp", "release_ms", v))
        k_makeup.valueChanged.connect(lambda v: self._set_fx("comp", "makeup_db", v))
        k_knee.valueChanged.connect(lambda v: self._set_fx("comp", "knee_db", v))
        for k in (k_thr, k_ratio, k_atk, k_rel, k_makeup, k_knee):
            comp_row.addWidget(k)
        comp_row.addStretch(1)
        root.addLayout(comp_row)

        # Presets
        root.addLayout(self._preset_row(
            self.DYN_PRESETS.keys(),
            lambda name: self._apply_dyn_preset(name),
        ))

        # --- Gate ---
        gate_header = self._fx_header(
            tr("veditor.sound_editor.dyn.gate"),
            "gate",
        )
        self._gate_enabled_btn = gate_header[1]
        root.addWidget(gate_header[0])

        gate_row = QHBoxLayout()
        gate_row.setSpacing(10)
        k_gthr = KnobWidget(
            label="Threshold", value=gate["threshold"], minimum=-80, maximum=0,
            default=-50, unit=" dB", color="blue", formatter=fmt_db,
        )
        k_gred = KnobWidget(
            label="Reduction", value=gate["reduction"], minimum=0, maximum=100,
            default=50, color="orange", formatter=lambda v: f"{v:.0f} %",
        )
        k_gthr.valueChanged.connect(lambda v: self._set_fx("gate", "threshold", v))
        k_gred.valueChanged.connect(lambda v: self._set_fx("gate", "reduction", v))
        gate_row.addWidget(k_gthr)
        gate_row.addWidget(k_gred)
        gate_row.addStretch(1)
        root.addLayout(gate_row)

        root.addStretch(1)
        return panel

    def _apply_dyn_preset(self, name: str) -> None:
        p = self.DYN_PRESETS.get(name) or {}
        c = self.clip.effects["comp"]
        c["threshold"] = p.get("thr", c["threshold"])
        c["ratio"]     = p.get("ratio", c["ratio"])
        c["attack_ms"] = p.get("atk", c["attack_ms"])
        c["release_ms"] = p.get("rel", c["release_ms"])
        c["makeup_db"] = p.get("makeup", c["makeup_db"])
        c["knee_db"]   = p.get("knee", c["knee_db"])
        c["enabled"] = True
        self._comp_enabled_btn.setChecked(True)
        self._rebuild_tab_ui()

    # ========= Effects tab =========

    FX_PRESETS: dict[str, dict] = {
        "Small Room":   {"type": "Room",   "size": 20, "decay": 0.8, "damp": 60, "mix": 20},
        "Concert Hall": {"type": "Hall",   "size": 80, "decay": 3.0, "damp": 30, "mix": 35},
        "Plate":        {"type": "Plate",  "size": 50, "decay": 2.0, "damp": 40, "mix": 30},
        "Spring":       {"type": "Spring", "size": 30, "decay": 1.5, "damp": 50, "mix": 25},
        "Slap Delay":   {"type": "Room",   "size": 15, "decay": 0.5, "damp": 50, "mix": 15,
                         "_delay": {"time_ms": 150, "feedback": 0, "mix": 40}},
    }

    def _build_effects_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget

        rev = self.clip.effects["reverb"]
        delay = self.clip.effects["delay"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # --- Reverb ---
        rev_header_row = QHBoxLayout()
        rev_header = self._fx_header(
            tr("veditor.sound_editor.fx.reverb"), "reverb"
        )
        self._rev_enabled_btn = rev_header[1]
        rev_header_row.addWidget(rev_header[0])

        # Type dropdown
        from PySide6.QtWidgets import QComboBox
        self._rev_type = QComboBox()
        self._rev_type.addItems(["Room", "Hall", "Plate", "Spring"])
        self._rev_type.setCurrentText(rev["type"])
        self._rev_type.currentTextChanged.connect(
            lambda t: self._set_fx("reverb", "type", t)
        )
        rev_header_row.addWidget(self._rev_type)
        rev_header_row.addStretch(1)
        root.addLayout(rev_header_row)

        rev_row = QHBoxLayout()
        rev_row.setSpacing(10)
        k_size = KnobWidget(
            label="Size", value=rev["size"], minimum=0, maximum=100,
            default=30, color="blue", formatter=lambda v: f"{v:.0f} %",
        )
        k_decay = KnobWidget(
            label="Decay", value=rev["decay_s"], minimum=0.1, maximum=10,
            default=1.5, color="blue", formatter=lambda v: f"{v:.1f} s",
        )
        k_damp = KnobWidget(
            label="Damping", value=rev["damping"], minimum=0, maximum=100,
            default=50, color="orange", formatter=lambda v: f"{v:.0f} %",
        )
        k_mix = KnobWidget(
            label="Mix", value=rev["mix"], minimum=0, maximum=100,
            default=20, color="green", formatter=lambda v: f"{v:.0f} %",
        )
        k_size.valueChanged.connect(lambda v: self._set_fx("reverb", "size", v))
        k_decay.valueChanged.connect(lambda v: self._set_fx("reverb", "decay_s", v))
        k_damp.valueChanged.connect(lambda v: self._set_fx("reverb", "damping", v))
        k_mix.valueChanged.connect(lambda v: self._set_fx("reverb", "mix", v))
        for k in (k_size, k_decay, k_damp, k_mix):
            rev_row.addWidget(k)
        rev_row.addStretch(1)
        root.addLayout(rev_row)

        root.addLayout(self._preset_row(
            self.FX_PRESETS.keys(),
            lambda name: self._apply_fx_preset(name),
        ))

        # --- Delay ---
        delay_header = self._fx_header(
            tr("veditor.sound_editor.fx.delay"), "delay"
        )
        self._delay_enabled_btn = delay_header[1]
        root.addWidget(delay_header[0])

        delay_row = QHBoxLayout()
        delay_row.setSpacing(10)
        k_time = KnobWidget(
            label="Time", value=delay["time_ms"], minimum=0, maximum=2000,
            default=250, color="blue", formatter=lambda v: f"{v:.0f} ms",
        )
        k_fb = KnobWidget(
            label="Feedback", value=delay["feedback"], minimum=0, maximum=95,
            default=30, color="orange", formatter=lambda v: f"{v:.0f} %",
        )
        k_dmix = KnobWidget(
            label="Mix", value=delay["mix"], minimum=0, maximum=100,
            default=20, color="green", formatter=lambda v: f"{v:.0f} %",
        )
        k_time.valueChanged.connect(lambda v: self._set_fx("delay", "time_ms", v))
        k_fb.valueChanged.connect(lambda v: self._set_fx("delay", "feedback", v))
        k_dmix.valueChanged.connect(lambda v: self._set_fx("delay", "mix", v))
        for k in (k_time, k_fb, k_dmix):
            delay_row.addWidget(k)
        delay_row.addStretch(1)
        root.addLayout(delay_row)

        root.addStretch(1)
        return panel

    def _apply_fx_preset(self, name: str) -> None:
        p = self.FX_PRESETS.get(name) or {}
        rev = self.clip.effects["reverb"]
        rev["type"] = p.get("type", rev["type"])
        rev["size"] = p.get("size", rev["size"])
        rev["decay_s"] = p.get("decay", rev["decay_s"])
        rev["damping"] = p.get("damp", rev["damping"])
        rev["mix"] = p.get("mix", rev["mix"])
        rev["enabled"] = True
        self._rev_enabled_btn.setChecked(True)
        # Slap Delay also drives the delay section.
        if "_delay" in p:
            d = self.clip.effects["delay"]
            d.update(p["_delay"])
            d["enabled"] = True
            self._delay_enabled_btn.setChecked(True)
        self._rebuild_tab_ui()

    # ========= Advanced tab =========

    def _build_advanced_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget, fmt_db, fmt_hz, fmt_speed
        deess = self.clip.effects["deesser"]
        ts = self.clip.effects["time_stretch"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # --- De-esser ---
        deess_header = self._fx_header(
            tr("veditor.sound_editor.adv.deesser"), "deesser"
        )
        self._deess_enabled_btn = deess_header[1]
        root.addWidget(deess_header[0])

        deess_row = QHBoxLayout()
        deess_row.setSpacing(10)
        k_dfreq = KnobWidget(
            label="Frequency", value=deess["freq"], minimum=2000, maximum=12000,
            default=6000, color="blue", logarithmic=True, formatter=fmt_hz,
        )
        k_dthr = KnobWidget(
            label="Threshold", value=deess["threshold"], minimum=-60, maximum=0,
            default=-30, unit=" dB", color="green", formatter=fmt_db,
        )
        k_dred = KnobWidget(
            label="Reduction", value=deess["reduction"], minimum=0, maximum=100,
            default=40, color="orange", formatter=lambda v: f"{v:.0f} %",
        )
        k_dfreq.valueChanged.connect(lambda v: self._set_fx("deesser", "freq", v))
        k_dthr.valueChanged.connect(lambda v: self._set_fx("deesser", "threshold", v))
        k_dred.valueChanged.connect(lambda v: self._set_fx("deesser", "reduction", v))
        for k in (k_dfreq, k_dthr, k_dred):
            deess_row.addWidget(k)
        deess_row.addStretch(1)
        root.addLayout(deess_row)

        # --- Time Stretch ---
        ts_header = self._fx_header(
            tr("veditor.sound_editor.adv.time_stretch"), "time_stretch"
        )
        self._ts_enabled_btn = ts_header[1]
        root.addWidget(ts_header[0])

        ts_row = QHBoxLayout()
        ts_row.setSpacing(10)
        k_ratio = KnobWidget(
            label="Ratio", value=ts["ratio"], minimum=0.5, maximum=2.0,
            default=1.0, color="orange", formatter=fmt_speed,
        )
        k_ratio.valueChanged.connect(lambda v: self._set_fx("time_stretch", "ratio", v))
        ts_row.addWidget(k_ratio)

        # Algorithm dropdown
        from PySide6.QtWidgets import QComboBox
        self._ts_algo = QComboBox()
        self._ts_algo.addItems(["atempo", "rubberband"])
        self._ts_algo.setCurrentText(ts.get("algorithm", "atempo"))
        self._ts_algo.currentTextChanged.connect(
            lambda t: self._set_fx("time_stretch", "algorithm", t)
        )
        algo_label = QLabel(tr("veditor.sound_editor.adv.algorithm"))
        algo_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")
        ts_row.addWidget(algo_label)
        ts_row.addWidget(self._ts_algo)
        ts_row.addStretch(1)
        root.addLayout(ts_row)

        # --- Markers list ---
        markers_label = QLabel(tr("veditor.sound_editor.adv.markers"))
        markers_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"font-weight: 700; letter-spacing: 1px; padding-top: 8px;"
        )
        root.addWidget(markers_label)

        from PySide6.QtWidgets import QListWidget
        self._markers_list = QListWidget()
        self._markers_list.setMaximumHeight(110)
        self._refresh_markers_list()
        # Jump to marker on double-click
        self._markers_list.itemDoubleClicked.connect(self._on_marker_list_dblclick)
        root.addWidget(self._markers_list)

        root.addStretch(1)
        return panel

    def _refresh_markers_list(self) -> None:
        if not hasattr(self, "_markers_list"):
            return
        self._markers_list.clear()
        for i, m_ms in enumerate(self._markers()):
            from PySide6.QtWidgets import QListWidgetItem
            it = QListWidgetItem(f"#{i + 1}   {_format_ms(int(m_ms))}")
            it.setData(Qt.ItemDataRole.UserRole, int(m_ms))
            self._markers_list.addItem(it)

    def _on_marker_list_dblclick(self, item) -> None:
        ms = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        try:
            self._player.setPosition(ms)
        except Exception:
            pass

    # ========= AI Master tab =========

    # Per-model tuning for AI-generated music. Values are percentages /
    # dB matching the AI Master knob ranges. ``width`` is bipolar with
    # 100 as the neutral center.
    AI_PRESETS: dict[str, dict] = {
        "Suno v3":    {"air": 5, "clarity": 60, "warmth": 40, "width": 130, "punch": 50, "excite": 70},
        "Suno v4":    {"air": 3, "clarity": 50, "warmth": 30, "width": 120, "punch": 40, "excite": 50},
        "Udio":       {"air": 4, "clarity": 45, "warmth": 35, "width": 110, "punch": 55, "excite": 60},
        "ACE-Step":   {"air": 6, "clarity": 55, "warmth": 50, "width": 140, "punch": 45, "excite": 75},
        "Generic AI": {"air": 4, "clarity": 50, "warmth": 40, "width": 120, "punch": 50, "excite": 60},
        "Custom":     {"air": 0, "clarity": 0,  "warmth": 0,  "width": 100, "punch": 0,  "excite": 0},
    }

    def _build_ai_master_tab(self) -> QWidget:
        from app.knob_widget import KnobWidget, fmt_db, fmt_percentage
        ai = self.clip.effects["ai_master"]

        panel = QWidget()
        panel.setObjectName("SEContent")
        root = QVBoxLayout(panel)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # --- One-Click Fix (preset buttons) ---
        preset_header = QLabel(tr("veditor.sound_editor.ai.one_click"))
        preset_header.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        root.addWidget(preset_header)

        # 6 preset buttons in a 3x2 grid — gives the AI-model labels
        # room to breathe without eating the knob row's vertical space.
        from PySide6.QtWidgets import QGridLayout
        preset_grid = QGridLayout()
        preset_grid.setSpacing(6)
        names = list(self.AI_PRESETS.keys())
        for idx, name in enumerate(names):
            b = QPushButton(name)
            b.setObjectName("SEAIPresetBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            # Highlight the currently-applied preset.
            if ai.get("preset") == name:
                b.setProperty("selected", True)
            b.clicked.connect(lambda _c, n=name: self._apply_ai_preset(n))
            preset_grid.addWidget(b, idx // 3, idx % 3)
        root.addLayout(preset_grid)

        # --- Detailed controls (6 macro knobs) ---
        ctrl_header = self._fx_header(
            tr("veditor.sound_editor.ai.detailed"),
            "ai_master",
        )
        self._ai_enabled_btn = ctrl_header[1]
        root.addWidget(ctrl_header[0])

        knob_row = QHBoxLayout()
        knob_row.setSpacing(10)

        k_air = KnobWidget(
            label="Air", value=float(ai["air"]),
            minimum=0, maximum=8, default=0, unit=" dB",
            color="green", formatter=fmt_db,
        )
        k_clarity = KnobWidget(
            label="Clarity", value=float(ai["clarity"]),
            minimum=0, maximum=100, default=0,
            color="blue", formatter=fmt_percentage,
        )
        k_warmth = KnobWidget(
            label="Warmth", value=float(ai["warmth"]),
            minimum=0, maximum=100, default=0,
            color="orange", formatter=fmt_percentage,
        )
        k_width = KnobWidget(
            label="Width", value=float(ai["width"]),
            minimum=0, maximum=200, default=100,
            color="green", bipolar=True, formatter=fmt_percentage,
        )
        k_punch = KnobWidget(
            label="Punch", value=float(ai["punch"]),
            minimum=0, maximum=100, default=0,
            color="blue", formatter=fmt_percentage,
        )
        k_excite = KnobWidget(
            label="Excite", value=float(ai["excite"]),
            minimum=0, maximum=100, default=0,
            color="orange", formatter=fmt_percentage,
        )

        # Any knob touch implies "user wants custom tuning" — mark the
        # preset state as Custom so the grid highlight doesn't lie.
        def _on_knob(field: str, value: float) -> None:
            self._set_fx("ai_master", field, float(value))
            if self.clip.effects["ai_master"].get("preset") != "Custom":
                self._set_fx("ai_master", "preset", "Custom")

        k_air.valueChanged.connect(lambda v: _on_knob("air", v))
        k_clarity.valueChanged.connect(lambda v: _on_knob("clarity", v))
        k_warmth.valueChanged.connect(lambda v: _on_knob("warmth", v))
        k_width.valueChanged.connect(lambda v: _on_knob("width", v))
        k_punch.valueChanged.connect(lambda v: _on_knob("punch", v))
        k_excite.valueChanged.connect(lambda v: _on_knob("excite", v))

        for k in (k_air, k_clarity, k_warmth, k_width, k_punch, k_excite):
            knob_row.addWidget(k)
        knob_row.addStretch(1)
        root.addLayout(knob_row)

        # --- Per-knob description strip (mirrors the HTML mock) ---
        desc_row = QHBoxLayout()
        desc_row.setSpacing(10)
        for key in ("air", "clarity", "warmth", "width", "punch", "excite"):
            lbl = QLabel(tr(f"veditor.sound_editor.ai.desc.{key}"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lbl.setWordWrap(True)
            lbl.setFixedWidth(88)
            lbl.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;"
            )
            desc_row.addWidget(lbl)
        desc_row.addStretch(1)
        root.addLayout(desc_row)

        # --- Hint / note ---
        note = QLabel(tr("veditor.sound_editor.ai.hint"))
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"padding-top: 6px;"
        )
        root.addWidget(note)

        root.addStretch(1)
        return panel

    def _apply_ai_preset(self, name: str) -> None:
        p = self.AI_PRESETS.get(name) or {}
        ai = self.clip.effects["ai_master"]
        for key in ("air", "clarity", "warmth", "width", "punch", "excite"):
            if key in p:
                ai[key] = float(p[key])
        ai["preset"] = name
        # Auto-enable unless the user explicitly picked Custom at zero.
        if name != "Custom":
            ai["enabled"] = True
        self._refresh_timeline_row()
        self._rebuild_tab_ui()

    # ========= shared helpers =========

    def _fx_header(self, title: str, fx_key: str) -> tuple[QWidget, QPushButton]:
        """Returns (header_row_widget, enable_toggle_button)."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 4, 0, 2)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        enabled_btn = QPushButton(tr("veditor.sound_editor.fx.enabled"))
        enabled_btn.setObjectName("SEActionBtn")
        enabled_btn.setCheckable(True)
        enabled_btn.setChecked(bool(self.clip.effects[fx_key].get("enabled")))
        enabled_btn.toggled.connect(lambda on, k=fx_key: self._set_fx(k, "enabled", on))
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(enabled_btn)
        return container, enabled_btn

    def _preset_row(self, names, callback) -> QHBoxLayout:
        r = QHBoxLayout()
        r.setSpacing(6)
        lbl = QLabel(tr("veditor.sound_editor.basic.presets"))
        lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        r.addWidget(lbl)
        for name in names:
            b = QPushButton(name)
            b.setObjectName("SEPresetBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c, n=name: callback(n))
            r.addWidget(b)
        r.addStretch(1)
        return r

    def _set_fx(self, fx_key: str, sub_key, value) -> None:
        """Write a nested effect-state value. ``sub_key`` may be a
        string (top-level) or a tuple (band, field) for the 3-band EQ."""
        fx = self.clip.effects[fx_key]
        if isinstance(sub_key, tuple):
            a, b = sub_key
            fx[a][b] = value
        else:
            fx[sub_key] = value
        # Refresh dependent views.
        if fx_key == "eq" and hasattr(self, "_eq_curve"):
            self._eq_curve.refresh()
        self._refresh_timeline_row()

    def _rebuild_tab_ui(self) -> None:
        """Preset application changes many knob values at once — the
        simplest way to keep every widget in sync is to rebuild the
        affected tab. Called after preset application."""
        current = self._tab_stack.currentIndex()
        # Rebuild just the stack panels (preserves title/waveform).
        # Replace each page with a freshly built one.
        new_panels = [
            self._build_basic_tab(),
            self._build_eq_tab(),
            self._build_dynamics_tab(),
            self._build_effects_tab(),
            self._build_advanced_tab(),
            self._build_ai_master_tab(),
        ]
        # Swap in place.
        for i in range(self._tab_stack.count()):
            old = self._tab_stack.widget(0)
            self._tab_stack.removeWidget(old)
            old.deleteLater()
        for p in new_panels:
            self._tab_stack.addWidget(p)
        self._tab_stack.setCurrentIndex(current)


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

        # Audio export quality dropdown — sits left of the export
        # button. Default = "standard" (44.1 kHz / 192 kbps / 16-bit),
        # which matches the Free tier ceiling.
        from app.audio_tracks import DEFAULT_AUDIO_QUALITY_ID
        self._audio_export_quality_id = DEFAULT_AUDIO_QUALITY_ID
        self._audio_quality_btn = QToolButton()
        self._audio_quality_btn.setObjectName("AudioQualityDropdown")
        self._audio_quality_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._audio_quality_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup,
        )
        self._audio_quality_btn.setToolTip(tr("veditor.export.quality.tooltip"))
        self._audio_quality_btn.setMinimumHeight(28)
        self._audio_quality_btn.setStyleSheet(
            f"QToolButton#AudioQualityDropdown {{ "
            f"background-color: {COLOR_BG_L2}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 3px 26px 3px 10px; font-size: 11px; }}"
            f"QToolButton#AudioQualityDropdown:hover {{ "
            f"background-color: {COLOR_BG_L5}; border-color: #5a5a62; }}"
            f"QToolButton#AudioQualityDropdown::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 8px; }}"
        )
        self._refresh_audio_quality_btn_label()
        self._build_audio_quality_menu()

        self._export_btn = QPushButton(tr("veditor.sound_editor.export"))
        self._export_btn.setObjectName("SEClose")
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setToolTip(tr("veditor.sound_editor.export.tooltip"))
        self._export_btn.clicked.connect(self._on_export_clicked)

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
        lay.addWidget(self._audio_quality_btn)
        lay.addWidget(self._export_btn)
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
        idx = {
            "basic": 0, "eq": 1, "dynamics": 2, "effects": 3,
            "advanced": 4, "ai_master": 5,
        }.get(tab_id, 0)
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
        self._refresh_markers_list()

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
            self._refresh_markers_list()

    def _apply_and_close(self) -> None:
        # All knob mutations already flow live; "Apply" is effectively
        # the same as "Close" today. Left as a separate button so the
        # upcoming effects tabs (which stage changes) have somewhere to
        # hook into.
        self._refresh_timeline_row()
        self.close()

    # ---- audio quality dropdown ----

    def _refresh_audio_quality_btn_label(self) -> None:
        from app.audio_tracks import get_audio_quality_preset
        from app import tier
        q = get_audio_quality_preset(self._audio_export_quality_id)
        label = tr(q.name_key)
        if tier.requires_pro(q.feature_id) and not tier.is_locked(q.feature_id):
            label = f"{label} ★"
        self._audio_quality_btn.setText(
            f"{tr('veditor.export.quality.label')}: {label}  ▾"
        )

    def _build_audio_quality_menu(self) -> None:
        from app.audio_tracks import AUDIO_QUALITY_PRESETS
        from app import tier
        menu = QMenu(self._audio_quality_btn)
        menu.setObjectName("AudioQualityMenu")
        menu.setStyleSheet(
            f"QMenu#AudioQualityMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#AudioQualityMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; "
            f"margin: 1px 0px; }}"
            f"QMenu#AudioQualityMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#AudioQualityMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#AudioQualityMenu::indicator {{ "
            f"width: 16px; height: 16px; left: 10px; }}"
        )
        for q in AUDIO_QUALITY_PRESETS:
            badge = ""
            if tier.requires_pro(q.feature_id):
                badge = "🔒 PRO  " if tier.is_locked(q.feature_id) else "★ PRO  "
            label = f"{badge}{tr(q.name_key)}  ·  {tr(q.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(q.id == self._audio_export_quality_id)
            act.triggered.connect(
                lambda _checked=False, qid=q.id: self._on_audio_quality_picked(qid)
            )
        self._audio_quality_btn.setMenu(menu)

    def _on_audio_quality_picked(self, quality_id: str) -> None:
        from app.audio_tracks import get_audio_quality_preset
        from app import tier
        q = get_audio_quality_preset(quality_id)
        if tier.is_locked(q.feature_id):
            self._show_audio_upsell(tr(q.name_key))
            self._build_audio_quality_menu()
            return
        self._audio_export_quality_id = quality_id
        self._refresh_audio_quality_btn_label()
        self._build_audio_quality_menu()

    def _show_audio_upsell(self, feature_label: str) -> None:
        """Modal upsell shown when a Free user picks a Pro-only audio
        format. Mirrors the video editor's upsell — same i18n keys."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            tr("upsell.title"),
            tr("upsell.body", feature=feature_label),
        )

    def _on_export_clicked(self) -> None:
        """Render the current clip (trim + cuts + fades + effects) to a
        standalone audio file. Free tier covers MP3 + WAV; Pro formats
        appear in the dialog with a "(PRO)" suffix and trigger an
        upsell when picked by a Free user."""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from app.audio_tracks import CLIP_EXPORT_FORMATS, ClipExporter
        from app import tier

        if self.clip.source_path is None:
            return

        # Free formats first (they're the only ones a Free user can
        # actually pick), Pro formats after — keeps the default useful
        # without hiding the upsell entirely.
        order = ["mp3", "wav", "flac", "alac", "aac", "ogg"]

        def _filter_for(key: str) -> str:
            base = CLIP_EXPORT_FORMATS[key]["filter"]
            fid = CLIP_EXPORT_FORMATS[key]["feature_id"]
            if tier.is_locked(fid):
                return base.replace("(*", "(PRO) (*")
            return base

        filters = [_filter_for(k) for k in order]
        all_filters = ";;".join(filters)

        src = Path(self.clip.source_path)
        # Default filename uses the first Free format (mp3) so save
        # dialogs land somewhere usable for everyone.
        default_name = str(src.with_name(f"{src.stem}_edited.mp3"))

        out_path, chosen_filter = QFileDialog.getSaveFileName(
            self,
            tr("veditor.sound_editor.export.dialog_title"),
            default_name,
            all_filters,
            filters[0],
        )
        if not out_path:
            return

        format_key = next(
            (k for k in order if _filter_for(k) == chosen_filter),
            "mp3",
        )

        # Pro-gating: if a Free user picked a locked format, show
        # upsell and abort instead of running the encode.
        feature_id = CLIP_EXPORT_FORMATS[format_key]["feature_id"]
        if tier.is_locked(feature_id):
            label = CLIP_EXPORT_FORMATS[format_key]["label"]
            self._show_audio_upsell(label)
            return

        # Make sure the extension on disk matches the chosen format —
        # users sometimes type a wrong extension in the save dialog.
        out_path_obj = Path(out_path)
        expected_ext = CLIP_EXPORT_FORMATS[format_key]["ext"]
        if out_path_obj.suffix.lower() != expected_ext.lower():
            out_path_obj = out_path_obj.with_suffix(expected_ext)

        # Disable the button so the user can't spam it. Re-enabled in
        # the completion/failure slots.
        self._export_btn.setEnabled(False)
        self._export_btn.setText(tr("veditor.sound_editor.export.running"))

        self._clip_exporter = ClipExporter(
            self.clip, str(out_path_obj), format_key, parent=self,
            quality_id=getattr(self, "_audio_export_quality_id", "standard"),
        )

        def _on_done(path: str) -> None:
            self._export_btn.setEnabled(True)
            self._export_btn.setText(tr("veditor.sound_editor.export"))
            QMessageBox.information(
                self,
                tr("veditor.sound_editor.export.success_title"),
                tr("veditor.sound_editor.export.success_body", path=path),
            )

        def _on_failed(reason: str) -> None:
            self._export_btn.setEnabled(True)
            self._export_btn.setText(tr("veditor.sound_editor.export"))
            QMessageBox.warning(
                self,
                tr("veditor.sound_editor.export.failed_title"),
                tr("veditor.sound_editor.export.failed_body", reason=reason),
            )

        self._clip_exporter.done.connect(_on_done)
        self._clip_exporter.failed.connect(_on_failed)
        self._clip_exporter.start()

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


class _EqCurveView(QWidget):
    """Simple magnitude-response preview for the 3-band EQ. Computes
    the summed response of three biquads (low-shelf / peak / high-
    shelf) on a log frequency grid and paints it as a filled curve.
    Not meant as a 1:1 match for ffmpeg's ``equalizer`` — it's a
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

        # Grid lines at 0 dB center + ±6 dB
        mid_y = rect.center().y()
        painter.setPen(QPen(QColor(40, 40, 48), 1))
        painter.drawLine(rect.left(), mid_y, rect.right(), mid_y)
        painter.setPen(QPen(QColor(30, 30, 38), 1, Qt.PenStyle.DashLine))
        painter.drawLine(rect.left(), mid_y - rect.height() // 4, rect.right(), mid_y - rect.height() // 4)
        painter.drawLine(rect.left(), mid_y + rect.height() // 4, rect.right(), mid_y + rect.height() // 4)

        # Log-frequency axis (20 Hz – 20 kHz)
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
            # ±12 dB spans ±h/2 ish; clamp.
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
        painter.fillPath(path, QColor(74, 155, 238, 60))

        # Curve line
        painter.setPen(QPen(QColor("#4a9bee"), 2))
        for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
            painter.drawLine(x1, y1, x2, y2)


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
        self._resizing_clip: AudioClip | None = None
        self._resize_side: str = ""
        self._resize_orig_start: int = 0
        self._resize_orig_end: int = 0
        self._waveform_errors: dict[int, str] = {}  # clip_id → reason
        # Hover tracking for audio-fade edge handles.
        self._hover_audio_fade_key: tuple | None = None    # (id(clip), id(fade))
        self._hover_audio_fade_side: str = ""

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
            self._resizing_clip = clip
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

        # Idle hover: cursor hinting + edge-handle hover highlight.
        prev_key = self._hover_audio_fade_key
        prev_side = self._hover_audio_fade_side
        hover_clip = self._clip_at_pos(pos)
        if hover_clip is not None:
            fade, side = self._fade_edge_at(hover_clip, x, pos.y())
            if fade is not None:
                self._hover_audio_fade_key = (id(hover_clip), id(fade))
                self._hover_audio_fade_side = side
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                if (prev_key != self._hover_audio_fade_key
                        or prev_side != self._hover_audio_fade_side):
                    self.update()
                return
        self._hover_audio_fade_key = None
        self._hover_audio_fade_side = ""
        if prev_key is not None:
            self.update()
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, _event) -> None:
        if self._hover_audio_fade_key is not None:
            self._hover_audio_fade_key = None
            self._hover_audio_fade_side = ""
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging_offset = False
        self._dragging_selection = False
        self._resizing_fade = None
        self._resizing_clip = None
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

        # Edge trim handles (always visible — DAW-style). Hover / drag
        # detection mirrors TrackRow's scheme.
        hover_key = (id(clip), id(fade))
        is_hover = self._hover_audio_fade_key == hover_key
        is_drag = (
            self._resizing_fade is fade
            and self._resizing_clip is clip
        )
        left_hot = (is_hover and self._hover_audio_fade_side == "left") \
            or (is_drag and self._resize_side == "left")
        right_hot = (is_hover and self._hover_audio_fade_side == "right") \
            or (is_drag and self._resize_side == "right")

        def _one(x: int, hot: bool) -> None:
            if is_drag and hot:
                w = 8; color = QColor("#ff7a4a")
            elif hot:
                w = 6; color = QColor("#ff7a4a")
            else:
                w = 4; color = QColor(255, 150, 80, 210)
            painter.fillRect(x - w // 2, bar_rect.top(), w, bar_rect.height(), color)
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
            n = max(2, w - 2)
            painter.drawLine(
                x - n // 2, bar_rect.top() + 2,
                x + n // 2, bar_rect.top() + 2,
            )
            painter.drawLine(
                x - n // 2, bar_rect.top() + bar_rect.height() - 3,
                x + n // 2, bar_rect.top() + bar_rect.height() - 3,
            )

        _one(fx1, left_hot)
        _one(fx2, right_hot)


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
        self._stickers: list = []             # list[Sticker]
        self._sticker_items: list = []        # list[StickerItem]
        # Label used to render the currently-active typography actor on
        # top of the preview. Phase 1 renders statically (no animations
        # yet). Actors themselves live on each VideoTrack.
        self._text_preview_label: QLabel | None = None

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

        # Export quality + format dropdowns sit left of the Export
        # button. Default: high quality / mp4 — matches the pre-tier
        # hardcoded values so existing exports stay byte-equivalent.
        from app.video_exporter import (
            DEFAULT_FORMAT_ID,
            DEFAULT_QUALITY_ID,
            EXPORT_FORMATS,
            QUALITY_PRESETS,
            get_export_format,
            get_quality_preset,
        )
        self._export_quality_id = DEFAULT_QUALITY_ID
        self._export_format_id = DEFAULT_FORMAT_ID
        self.quality_btn = QToolButton()
        self.quality_btn.setObjectName("QualityDropdown")
        self.quality_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quality_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.quality_btn.setToolTip(tr("veditor.export.quality.tooltip"))
        self.quality_btn.setMinimumHeight(30)
        # Inline style so the QToolButton matches the dark dialog theme
        # (the global ``QPushButton#ToolButton`` rule does not target
        # QToolButton) and the dropdown arrow gets enough breathing room.
        self.quality_btn.setStyleSheet(
            f"QToolButton#QualityDropdown {{ "
            f"background-color: {COLOR_BG_L2}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 28px 4px 12px; font-size: 12px; }}"
            f"QToolButton#QualityDropdown:hover {{ "
            f"background-color: {COLOR_BG_L5}; border-color: #5a5a62; }}"
            f"QToolButton#QualityDropdown::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 8px; }}"
        )
        self._refresh_quality_btn_label()
        self._build_quality_menu()

        # Format dropdown — sibling of quality_btn, identical styling.
        self.format_btn = QToolButton()
        self.format_btn.setObjectName("FormatDropdown")
        self.format_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.format_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.format_btn.setToolTip(tr("veditor.export.format.tooltip"))
        self.format_btn.setMinimumHeight(30)
        self.format_btn.setStyleSheet(
            f"QToolButton#FormatDropdown {{ "
            f"background-color: {COLOR_BG_L2}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 4px 28px 4px 12px; font-size: 12px; }}"
            f"QToolButton#FormatDropdown:hover {{ "
            f"background-color: {COLOR_BG_L5}; border-color: #5a5a62; }}"
            f"QToolButton#FormatDropdown::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 8px; }}"
        )
        self._refresh_format_btn_label()
        self._build_format_menu()

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
        toolbar.addWidget(self.format_btn)
        toolbar.addWidget(self.quality_btn)
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

        # --- Transitions row — Fade / Typography / Speed drag cards ---
        track_bar.addWidget(self._build_fade_card())
        self.typo_card = TypographyCard()
        track_bar.addWidget(self.typo_card)
        self.speed_card = SpeedCard()
        track_bar.addWidget(self.speed_card)
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

        # --- Selection / clear-selection row (controls bar) ---
        # Speed-rate buttons used to live here too, but the SpeedCard
        # (drag-drop) and right-click context menu cover the same
        # workflow with less clutter, so the buttons were removed.
        # ``_speed_buttons`` stays as an empty list so the existing
        # selection-state update loop is a no-op rather than a bug.
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

        self.clear_sel_btn = QPushButton(tr("veditor.btn.clear_selection"))
        self.clear_sel_btn.setObjectName("ToolButton")
        self.clear_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_sel_btn.setEnabled(False)
        self.clear_sel_btn.clicked.connect(self._clear_selection_active_track)
        sel_row.addWidget(self.clear_sel_btn)
        root.addWidget(controls_bar)

        # --- Color grading section ---
        root.addWidget(
            self._make_section_header(tr("veditor.section.color"), "color")
        )
        root.addWidget(self._build_color_grading_panel())

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
        row.speed_changed.connect(self._on_track_speed_changed)
        row.media_dropped.connect(self._on_media_dropped_on_video_row)
        row.typography_double_clicked.connect(self._open_typography_editor)
        row.typography_context_menu.connect(self._show_typography_menu)
        row.typography_changed.connect(self._on_typography_changed)
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
        # Color grading is per-track — re-sync the panel so the
        # sliders/preset reflect whatever the new active track has.
        if hasattr(self, "_color_sliders"):
            self._sync_color_panel()

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

    def _on_track_speed_changed(self, _track_id: int) -> None:
        # Speed segments affect the player's duration / seek mapping,
        # so refresh the player's cache. The row has already repainted.
        self._refresh_player_tracks()
        self._update_tracks_host_width()

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

        # Hide preview bubble / sticker items while editing in the
        # dialog; respawn after so the dialog owns the interactive
        # version during the edit.
        for item in list(self._bubble_items):
            item.deleteLater()
        self._bubble_items.clear()
        for item in list(self._sticker_items):
            item.deleteLater()
        self._sticker_items.clear()

        dlg = PaintDialog(
            background_pixmap=self._preview_pixmap,
            initial_strokes=self._strokes,
            time_ms=self._player.position(),
            parent=self,
            initial_bubbles=self._bubbles,
            initial_stickers=self._stickers,
        )
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._strokes = dlg.result_strokes()
            self._bubbles = dlg.result_bubbles()
            self._stickers = dlg.result_stickers()
            self._drawing_canvas.update()
        # Respawn passive items so the user sees bubbles / stickers on
        # the preview.
        for sticker in self._stickers:
            self._spawn_sticker_item(sticker)
        for bubble in self._bubbles:
            self._spawn_bubble_item(bubble)
        self._update_bubble_visibility(self._player.position())
        self._update_sticker_visibility(self._player.position())

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

    # ------------- stickers -------------

    def _spawn_sticker_item(self, sticker):
        from app.drawing import StickerItem
        item = StickerItem(sticker, self._drawing_canvas)
        item.sync_to_parent()
        item.show()
        item.moved.connect(lambda it=item: it.sync_to_sticker())
        item.deleted.connect(lambda it=item, s=sticker: self._remove_sticker(s, it))
        item.duplicated.connect(lambda s=sticker: self._duplicate_sticker(s))
        item.raise_requested.connect(lambda s=sticker: self._reorder_sticker(s, +1))
        item.lower_requested.connect(lambda s=sticker: self._reorder_sticker(s, -1))
        self._sticker_items.append(item)
        # Bubbles stay on top of stickers.
        for b_item in self._bubble_items:
            b_item.raise_()
        return item

    def _remove_sticker(self, sticker, item) -> None:
        try:
            self._stickers.remove(sticker)
        except ValueError:
            pass
        try:
            self._sticker_items.remove(item)
        except ValueError:
            pass
        item.deleteLater()

    def _duplicate_sticker(self, sticker) -> None:
        import copy
        dup = copy.deepcopy(sticker)
        dup.x_norm = min(0.95, dup.x_norm + 0.03)
        dup.y_norm = min(0.95, dup.y_norm + 0.03)
        current_max = max((s.z_index for s in self._stickers), default=0)
        dup.z_index = current_max + 1
        self._stickers.append(dup)
        self._spawn_sticker_item(dup)
        self._update_sticker_visibility(self._player.position())

    def _reorder_sticker(self, sticker, direction: int) -> None:
        if direction > 0:
            sticker.z_index = max(
                (s.z_index for s in self._stickers if s is not sticker),
                default=0,
            ) + 1
        else:
            sticker.z_index = min(
                (s.z_index for s in self._stickers if s is not sticker),
                default=0,
            ) - 1
        self._sticker_items.sort(key=lambda it: int(it.sticker.z_index))
        for it in self._sticker_items:
            it.raise_()
        for b_item in self._bubble_items:
            b_item.raise_()

    def _resync_stickers_to_preview(self) -> None:
        for item in self._sticker_items:
            item.sync_to_parent()

    def _update_sticker_visibility(self, pos_ms: int) -> None:
        from app.drawing import _sticker_active
        t = int(pos_ms)
        for item in self._sticker_items:
            item.setVisible(_sticker_active(item.sticker, t))

    # ------------- typography (Phase 1) -------------

    def _ensure_text_preview_label(self) -> QLabel:
        """Lazily create the QLabel used to render the active text
        clip on top of the preview. Parented to the drawing canvas so
        it shares the canvas's coordinate system (which already maps
        1:1 with the video rect)."""
        if self._text_preview_label is None:
            lbl = QLabel(self._drawing_canvas)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("background: transparent; color: white;")
            lbl.hide()
            self._text_preview_label = lbl
        return self._text_preview_label

    def _find_typography_actor(self, clip_id: int) -> "tuple[VideoTrack, TextClip] | None":
        """Locate a typography actor by its id across every video track."""
        for track in self._tracks:
            for clip in getattr(track, "typography_actors", []):
                if clip.id == clip_id:
                    return track, clip
        return None

    def _update_text_clip_overlay(self, pos_ms: int) -> None:
        """Show / hide / restyle the preview text based on active
        typography actors at ``pos_ms``. Phase 1: static render of the
        topmost active actor (no animations yet).

        Typography actors live per-VideoTrack in track-local source ms.
        Active-check: track-local time = project_ms - track.offset_ms,
        valid when 0 <= local < track.duration_ms and actor.contains(local).
        """
        lbl = self._ensure_text_preview_label()
        project_ms = int(pos_ms)

        active: list[TextClip] = []
        for track in self._tracks:
            if track.source_path is None or track.duration_ms <= 0:
                continue
            local = project_ms - int(track.offset_ms)
            if local < 0 or local >= track.duration_ms:
                continue
            for clip in getattr(track, "typography_actors", []):
                if clip.contains(local):
                    active.append(clip)

        if not active:
            lbl.hide()
            return

        # Last registered wins — drawn on top. Future phases may honor
        # per-actor z-order the way stickers do.
        clip = active[-1]
        style = clip.style
        canvas = self._drawing_canvas
        cw, ch = canvas.width(), canvas.height()
        if cw <= 0 or ch <= 0:
            lbl.hide()
            return

        font = QFont(style.font_family, int(style.font_size * ch / 1080.0))
        font.setWeight(QFont.Weight(int(style.font_weight)))
        lbl.setFont(font)
        lbl.setStyleSheet(
            f"background: transparent; color: {style.color};"
            " font-weight: 700;"
        )
        lbl.setText(clip.display_text())
        lbl.adjustSize()

        lw = min(int(cw * 0.9), max(40, lbl.width()))
        lh = max(30, lbl.height())
        cx = int(style.position_x * cw)
        cy = int(style.position_y * ch)
        lbl.setGeometry(cx - lw // 2, cy - lh // 2, lw, lh)
        lbl.show()
        lbl.raise_()

    def _on_typography_changed(self, track_id: int) -> None:
        """Called after any drag/resize/drop/add/remove of a typography
        actor on any video track."""
        self._update_tracks_host_width()
        self._update_text_clip_overlay(self._player.position())

    def _open_typography_editor(self, track_id: int, clip_id: int) -> None:
        """Double-click handler — opens the (Phase 1 stub) editor for
        the typography actor. Phase 2 replaces this with the full 3-pane
        modal."""
        found = self._find_typography_actor(clip_id)
        if found is None:
            return
        _track, clip = found
        dlg = TypographyEditorDialog(clip, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._update_text_clip_overlay(self._player.position())

    def _show_typography_menu(self, track_id: int, clip_id: int, global_pos) -> None:
        from PySide6.QtWidgets import QMenu

        found = self._find_typography_actor(clip_id)
        if found is None:
            return
        track, clip = found
        menu = QMenu(self)
        a_edit = menu.addAction(tr("veditor.typo_menu.edit"))
        a_dup = menu.addAction(tr("veditor.typo_menu.duplicate"))
        menu.addSeparator()
        a_del = menu.addAction(tr("veditor.typo_menu.delete"))

        chosen = menu.exec(global_pos)
        if chosen is a_edit:
            self._open_typography_editor(track_id, clip_id)
        elif chosen is a_dup:
            import copy
            dup = copy.deepcopy(clip)
            from app.typography import _next_id
            dup.id = _next_id()
            # Nudge so the copy shows up after the original.
            dup.start_ms = clip.end_ms
            dup.end_ms = dup.start_ms + clip.duration_ms
            if dup.end_ms > track.duration_ms:
                dup.end_ms = track.duration_ms
                dup.start_ms = max(0, dup.end_ms - clip.duration_ms)
            track.typography_actors.append(dup)
            track.typography_actors.sort(key=lambda c: c.start_ms)
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._on_typography_changed(track_id)
        elif chosen is a_del:
            track.typography_actors = [
                c for c in track.typography_actors if c.id != clip_id
            ]
            row = self._track_rows.get(track_id)
            if row is not None:
                row.update()
            self._on_typography_changed(track_id)

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
        self._resync_stickers_to_preview()
        # Re-layout the active text clip overlay on canvas resize.
        if hasattr(self, "_text_track"):
            self._update_text_clip_overlay(self._player.position())
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
        # Bubbles, stickers, and text clips gate on the current playhead
        self._update_bubble_visibility(pos)
        self._update_sticker_visibility(pos)
        self._update_text_clip_overlay(pos)

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

    # ---- export quality dropdown ----

    def _refresh_quality_btn_label(self) -> None:
        from app.video_exporter import get_quality_preset
        from app import tier
        q = get_quality_preset(self._export_quality_id)
        label = tr(q.name_key)
        if tier.requires_pro(q.feature_id) and not tier.is_locked(q.feature_id):
            label = f"{label} ★"          # PRO unlocked
        self.quality_btn.setText(f"{tr('veditor.export.quality.label')}: {label}  ▾")

    def _build_quality_menu(self) -> None:
        from app.video_exporter import QUALITY_PRESETS
        from app import tier
        menu = QMenu(self.quality_btn)
        menu.setObjectName("QualityMenu")
        # Override the default menu look with explicit padding, larger
        # font, and a strong accent for the currently-selected row so
        # the active quality is obvious at a glance.
        menu.setStyleSheet(
            f"QMenu#QualityMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#QualityMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; "
            f"margin: 1px 0px; }}"
            f"QMenu#QualityMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#QualityMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#QualityMenu::indicator {{ "
            f"width: 16px; height: 16px; left: 10px; }}"
        )
        for q in QUALITY_PRESETS:
            badge = ""
            if tier.requires_pro(q.feature_id):
                badge = "🔒 PRO  " if tier.is_locked(q.feature_id) else "★ PRO  "
            label = f"{badge}{tr(q.name_key)}  ·  {tr(q.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(q.id == self._export_quality_id)
            act.triggered.connect(
                lambda _checked=False, qid=q.id: self._on_quality_picked(qid)
            )
        self.quality_btn.setMenu(menu)

    def _on_quality_picked(self, quality_id: str) -> None:
        from app.video_exporter import get_quality_preset
        from app import tier
        q = get_quality_preset(quality_id)
        if tier.is_locked(q.feature_id):
            self._show_upsell(q.feature_id, tr(q.name_key))
            # Rebuild the menu so the previous selection's checkmark
            # is restored (the click toggled it off).
            self._build_quality_menu()
            return
        self._export_quality_id = quality_id
        self._refresh_quality_btn_label()
        self._build_quality_menu()

    # ---- export format dropdown ----

    def _refresh_format_btn_label(self) -> None:
        from app.video_exporter import get_export_format
        from app import tier
        f = get_export_format(self._export_format_id)
        label = tr(f.name_key)
        if tier.requires_pro(f.feature_id) and not tier.is_locked(f.feature_id):
            label = f"{label} ★"
        self.format_btn.setText(f"{tr('veditor.export.format.label')}: {label}  ▾")

    def _build_format_menu(self) -> None:
        from app.video_exporter import EXPORT_FORMATS
        from app import tier
        menu = QMenu(self.format_btn)
        menu.setObjectName("FormatMenu")
        menu.setStyleSheet(
            f"QMenu#FormatMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#FormatMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; "
            f"margin: 1px 0px; }}"
            f"QMenu#FormatMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#FormatMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#FormatMenu::indicator {{ "
            f"width: 16px; height: 16px; left: 10px; }}"
        )
        for f in EXPORT_FORMATS:
            badge = ""
            if tier.requires_pro(f.feature_id):
                badge = "🔒 PRO  " if tier.is_locked(f.feature_id) else "★ PRO  "
            label = f"{badge}{tr(f.name_key)}  ·  {tr(f.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(f.id == self._export_format_id)
            act.triggered.connect(
                lambda _checked=False, fid=f.id: self._on_format_picked(fid)
            )
        self.format_btn.setMenu(menu)

    def _on_format_picked(self, format_id: str) -> None:
        from app.video_exporter import get_export_format
        from app import tier
        f = get_export_format(format_id)
        if tier.is_locked(f.feature_id):
            self._show_upsell(f.feature_id, tr(f.name_key))
            self._build_format_menu()
            return
        self._export_format_id = format_id
        self._refresh_format_btn_label()
        self._build_format_menu()

    def _show_upsell(self, feature_id: str, feature_label: str) -> None:
        """Generic upsell modal — used whenever a Pro-only control is
        triggered by a Free user. Title + body i18n keys are shared,
        but the body interpolates the specific feature label."""
        QMessageBox.information(
            self,
            tr("upsell.title"),
            tr("upsell.body", feature=feature_label),
        )

    # ---- color grading panel ----

    def _build_color_grading_panel(self) -> QWidget:
        """DaVinci-style 3-wheel grading panel.

        Layout:
        ``[Preset ▾]  ............  [Reset]``
        ``[Shadows wheel] [Midtones wheel] [Highlights wheel]``
        ``Brightness slider``
        ``Contrast   slider``
        ``Saturation slider``
        """
        host = QWidget()
        host.setObjectName("ColorPanel")
        outer = QVBoxLayout(host)
        outer.setContentsMargins(12, 8, 12, 10)
        outer.setSpacing(8)

        # ---- Top row: preset picker + reset ----
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)

        self._color_preset_btn = QToolButton()
        self._color_preset_btn.setObjectName("ColorPresetDropdown")
        self._color_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_preset_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup,
        )
        self._color_preset_btn.setMinimumHeight(28)
        self._color_preset_btn.setStyleSheet(
            f"QToolButton#ColorPresetDropdown {{ "
            f"background-color: {COLOR_BG_L2}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
            f"padding: 3px 26px 3px 10px; font-size: 11px; }}"
            f"QToolButton#ColorPresetDropdown:hover {{ "
            f"background-color: {COLOR_BG_L5}; border-color: #5a5a62; }}"
            f"QToolButton#ColorPresetDropdown::menu-indicator {{ "
            f"image: none; subcontrol-origin: padding; "
            f"subcontrol-position: right center; right: 8px; }}"
        )
        head.addWidget(self._color_preset_btn)
        head.addStretch(1)

        reset_btn = QPushButton(tr("color.reset"))
        reset_btn.setObjectName("ToolButton")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._on_color_reset)
        head.addWidget(reset_btn)

        outer.addLayout(head)

        # ---- Wheels row: Shadows / Midtones / Highlights ----
        # Tight spacing + horizontal centring. The wheels are fixed-size
        # widgets, so leaving stretches on either side keeps them from
        # smearing across the whole pane width.
        wheels_row = QHBoxLayout()
        wheels_row.setContentsMargins(0, 4, 0, 4)
        wheels_row.setSpacing(4)
        wheels_row.addStretch(1)
        self._color_wheels: dict[str, _ColorWheelWidget] = {}
        wheel_specs = (
            ("shadows", "color.wheel.shadows"),
            ("midtones", "color.wheel.midtones"),
            ("highlights", "color.wheel.highlights"),
        )
        for region, label_key in wheel_specs:
            wheel = _ColorWheelWidget(label=tr(label_key))
            wheel.value_changed.connect(
                lambda x, y, r=region: self._on_color_wheel_changed(r, x, y)
            )
            wheels_row.addWidget(wheel, 0)
            self._color_wheels[region] = wheel
        wheels_row.addStretch(1)
        outer.addLayout(wheels_row)

        # ---- Knobs: brightness / contrast / saturation ----
        # Bipolar knobs (centred at 0) match the sound editor's UI
        # vocabulary, so the editor reads as one consistent surface.
        # Drag = adjust, double-click = reset to 0, right-click = type
        # an exact value, mouse wheel = small steps.
        from app.knob_widget import KnobWidget

        def _signed_pct(v: float) -> str:
            n = int(round(v))
            return f"{n:+d}" if n != 0 else "0"

        knobs_row = QHBoxLayout()
        knobs_row.setContentsMargins(0, 4, 0, 0)
        knobs_row.setSpacing(6)
        knobs_row.addStretch(1)

        # Reuse ``self._color_sliders`` as the dict name even though the
        # values are now KnobWidget instances — _sync_color_panel and
        # _on_color_slider_changed only call .blockSignals/.setValue/
        # .value(), all of which the knob exposes too. Keeps the rest
        # of the panel code unchanged.
        self._color_sliders: dict = {}
        self._color_readouts: dict = {}        # unused with knobs
        knob_specs = (
            ("brightness", "color.slider.brightness", "blue"),
            ("contrast",   "color.slider.contrast",   "blue"),
            ("saturation", "color.slider.saturation", "green"),
        )
        for key, label_key, color in knob_specs:
            knob = KnobWidget(
                label=tr(label_key),
                value=0.0,
                minimum=-100.0,
                maximum=100.0,
                default=0.0,
                color=color,
                bipolar=True,
                formatter=_signed_pct,
            )
            knob.valueChanged.connect(
                lambda v, k=key: self._on_color_slider_changed(k, int(round(v)))
            )
            knobs_row.addWidget(knob, 0)
            self._color_sliders[key] = knob
        knobs_row.addStretch(1)
        outer.addLayout(knobs_row)

        self._build_color_preset_menu()
        self._sync_color_panel()
        return host

    def _active_color_grade(self):
        """Return the active track's ``ColorGrade``, creating one on the
        track if missing. Returns ``None`` when no track is active."""
        track = self._active_track()
        if track is None:
            return None
        if getattr(track, "color_grade", None) is None:
            from app.color_grading import ColorGrade
            track.color_grade = ColorGrade()
        return track.color_grade

    def _sync_color_panel(self) -> None:
        """Pull current track's grade into wheels + knobs + preset
        label. Blocks signals so this isn't recorded as a user-driven
        change. Safe to call before a track exists."""
        grade = self._active_color_grade()
        for key, knob in getattr(self, "_color_sliders", {}).items():
            value = int(getattr(grade, key)) if grade is not None else 0
            knob.blockSignals(True)
            knob.setValue(float(value), emit=False)
            knob.blockSignals(False)
        for region, wheel in getattr(self, "_color_wheels", {}).items():
            if grade is not None:
                x = int(getattr(grade, f"{region}_x"))
                y = int(getattr(grade, f"{region}_y"))
            else:
                x = y = 0
            wheel.set_value(x, y, emit=False)
        self._refresh_color_preset_btn_label()
        self._build_color_preset_menu()

    def _on_color_slider_changed(self, key: str, value: int) -> None:
        grade = self._active_color_grade()
        if grade is None:
            return
        setattr(grade, key, int(value))
        # Any manual knob drag detaches the grade from a named preset.
        if grade.preset_id != "none":
            grade.preset_id = "custom"
        self._refresh_color_preset_btn_label()
        # Re-render the current frame so the preview reflects the change.
        self._player.set_position(self._player.position())

    def _on_color_wheel_changed(self, region: str, x: int, y: int) -> None:
        grade = self._active_color_grade()
        if grade is None:
            return
        setattr(grade, f"{region}_x", int(x))
        setattr(grade, f"{region}_y", int(y))
        if grade.preset_id != "none":
            grade.preset_id = "custom"
        self._refresh_color_preset_btn_label()
        self._player.set_position(self._player.position())

    def _on_color_reset(self) -> None:
        grade = self._active_color_grade()
        if grade is None:
            return
        grade.reset()
        self._sync_color_panel()
        self._player.set_position(self._player.position())

    def _refresh_color_preset_btn_label(self) -> None:
        from app.color_grading import get_preset
        grade = self._active_color_grade()
        if grade is None:
            label = tr("color.preset.none")
        elif grade.preset_id == "custom":
            label = tr("color.preset.custom")
        else:
            label = tr(get_preset(grade.preset_id).name_key)
        self._color_preset_btn.setText(
            f"{tr('color.preset.label')}: {label}  ▾"
        )

    def _build_color_preset_menu(self) -> None:
        from app.color_grading import COLOR_PRESETS
        from app import tier
        menu = QMenu(self._color_preset_btn)
        menu.setObjectName("ColorPresetMenu")
        menu.setStyleSheet(
            f"QMenu#ColorPresetMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#ColorPresetMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; margin: 1px 0px; }}"
            f"QMenu#ColorPresetMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#ColorPresetMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
        )
        grade = self._active_color_grade()
        current_id = grade.preset_id if grade is not None else "none"
        for p in COLOR_PRESETS:
            badge = ""
            if tier.requires_pro(p.feature_id):
                badge = "🔒 PRO  " if tier.is_locked(p.feature_id) else "★ PRO  "
            label = f"{p.icon}  {badge}{tr(p.name_key)}  ·  {tr(p.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(p.id == current_id)
            act.triggered.connect(
                lambda _checked=False, pid=p.id: self._on_color_preset_picked(pid)
            )
        self._color_preset_btn.setMenu(menu)

    def _on_color_preset_picked(self, preset_id: str) -> None:
        from app.color_grading import apply_preset, get_preset
        from app import tier
        p = get_preset(preset_id)
        if tier.is_locked(p.feature_id):
            self._show_upsell(p.feature_id, tr(p.name_key))
            self._build_color_preset_menu()
            return
        grade = self._active_color_grade()
        if grade is None:
            return
        apply_preset(grade, preset_id)
        self._sync_color_panel()
        self._player.set_position(self._player.position())

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

        from app.video_exporter import get_export_format
        fmt = get_export_format(getattr(self, "_export_format_id", "mp4"))
        default_name = f"{track.source_path.stem}_edited{fmt.extension}"
        default_path = track.source_path.parent / default_name
        filter_str = tr(f"veditor.export.filter.{fmt.id}")
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("veditor.export.dialog_title"),
            str(default_path),
            filter_str,
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != fmt.extension:
            out = out.with_suffix(fmt.extension)

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

        # Typography actors live per-VideoTrack in track-local source
        # ms. Pass the active track's actors as (start, end, clip)
        # tuples — they'll be rendered to alpha MOVs and overlaid by
        # the exporter. (Phase 5b: support actors on inactive tracks
        # via project-time mapping.)
        from app import tier
        all_actors = [
            (actor.start_ms, actor.end_ms, actor)
            for actor in getattr(track, "typography_actors", [])
            if actor.end_ms > actor.start_ms
        ]
        if all_actors and tier.is_locked("export.typography"):
            # Free user has typography placed but it can't ship in the
            # rendered file. Confirm before stripping so they know why
            # the output looks different from preview.
            choice = QMessageBox.warning(
                self,
                tr("upsell.title"),
                tr("export.typography.locked.body", count=len(all_actors)),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Ok,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            text_actors_source: list = []
        else:
            text_actors_source = all_actors

        thread = VideoExportThread(
            track.source_path,
            out,
            segments,
            self._subtitle_panel.subtitles(),
            self._strokes,
            cuts=track.cuts,
            fade_segments=track.fades,
            bubbles=self._bubbles,
            stickers=self._stickers,
            audio_tracks=[t for t in self._audio_tracks if t.is_loaded],
            text_actors_source=text_actors_source,
            quality_id=getattr(self, "_export_quality_id", "high"),
            format_id=getattr(self, "_export_format_id", "mp4"),
            color_grade=getattr(track, "color_grade", None),
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


def _format_speed(p: float) -> str:
    """Format a speed factor as '2x' or '0.5x' for UI labels."""
    if abs(p - round(p)) < 1e-3:
        return f"{int(round(p))}x"
    return f"{p:g}x"


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"
