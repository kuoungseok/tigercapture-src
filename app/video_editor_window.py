from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QThread, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
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
        if event.mimeData().hasFormat(FADE_MIME_TYPE):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(FADE_MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat(FADE_MIME_TYPE):
            return
        try:
            duration_ms = int(bytes(event.mimeData().data(FADE_MIME_TYPE)).decode("utf-8"))
        except Exception:
            duration_ms = FadeCard.DEFAULT_DURATION_MS
        duration_ms = max(100, duration_ms)
        if self.track.duration_ms <= 0:
            return
        # Drop position → center of the new fade segment in track-local ms.
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

        self._player = ProjectPlayer(self)
        self._player.frame_ready.connect(self._on_frame_ready)
        self._player.position_changed.connect(self._on_position_changed)
        self._player.duration_changed.connect(self._on_duration_changed)
        self._player.state_changed.connect(self._on_playback_state_changed)
        self._player.error_occurred.connect(self._on_player_error)

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
        root.addWidget(
            self._make_section_header(tr("veditor.section.preview"), "preview")
        )
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

        transport.addWidget(self.play_btn)
        transport.addWidget(self.time_label)
        transport.addStretch(1)
        transport.addWidget(self.current_speed_label)
        root.addWidget(play_bar)

        # --- Timeline section ---
        root.addWidget(
            self._make_section_header(tr("veditor.section.timeline"), "timeline")
        )

        # --- Track-management bar (sits right above the track view) ---
        track_bar = QHBoxLayout()
        track_bar.setContentsMargins(0, 0, 0, 0)
        track_bar.setSpacing(6)
        track_bar.addWidget(self.add_track_btn)
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
        self._track_rows[track.id] = row
        self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, row)
        self._update_tracks_host_width()

    def _update_tracks_host_width(self) -> None:
        # Start with baseline (ruler) and each track's own preferred width.
        max_w = max(MIN_TRACK_WIDTH, self._timeline_ruler.desired_width())
        # Consider each row's natural duration-driven width.
        for row in self._track_rows.values():
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
        self._tracks_host.setMinimumWidth(max_w)

    def _change_zoom(self, factor: float) -> None:
        new_px = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, self._px_per_sec * factor))
        if abs(new_px - self._px_per_sec) < 0.001:
            return
        self._px_per_sec = new_px
        for row in self._track_rows.values():
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
        if self._active_track_id is None or len(self._tracks) <= 1:
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
        self._player.refresh_tracks(self._tracks)

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
        act_delete = menu.addAction(tr("veditor.menu.delete_track"))
        act_delete.setEnabled(len(self._tracks) > 1)

        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        if chosen is act_load:
            self._load_into_track(track_id)
        elif chosen is act_cut:
            self._cut_selection_in_track(track_id)
        elif chosen in speed_actions:
            self._apply_speed_to_selection(speed_actions[chosen])
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
