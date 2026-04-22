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

from app.drawing import DrawingCanvas, Stroke
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

    def contains(self, ms: int) -> bool:
        return self.start_ms <= ms < self.end_ms


@dataclass
class VideoTrack:
    id: int
    source_path: Path | None = None
    duration_ms: int = 0
    speed_segments: list[SpeedSegment] = field(default_factory=list)
    cuts: list[CutSegment] = field(default_factory=list)
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


class TrackRow(QWidget):
    """Single horizontal track with label row + timeline row."""

    clicked = Signal(int)  # track_id
    position_requested = Signal(int, int)  # track_id, ms
    selection_changed = Signal(int, int, int)  # track_id, start, end
    context_menu = Signal(int, QPoint)  # track_id, global_pos

    MARGIN = 10
    LABEL_H = 18
    TIMELINE_H = TRACK_HEIGHT

    def __init__(self, track: VideoTrack) -> None:
        super().__init__()
        self.track = track
        self._is_active: bool = False
        self._position_ms: int = 0
        self._dragging_selection: bool = False
        self._dragging_playhead: bool = False
        self._drag_start_ms: int = 0
        self._px_per_sec: float = DEFAULT_PX_PER_SEC

        self.setFixedHeight(self.LABEL_H + self.TIMELINE_H + TRACK_V_PADDING)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._recalc_width()

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self._recalc_width()

    def _recalc_width(self) -> None:
        if self.track.duration_ms <= 0:
            w = MIN_TRACK_WIDTH
        else:
            w = int(self.track.duration_ms / 1000.0 * self._px_per_sec) + 2 * self.MARGIN
            w = max(MIN_TRACK_WIDTH, w)
        self.setFixedWidth(w)
        self.update()

    def set_active(self, active: bool) -> None:
        if self._is_active != active:
            self._is_active = active
            self.update()

    def set_position(self, ms: int) -> None:
        if self._is_active:
            self._position_ms = ms
            self.update()

    def _timeline_rect(self) -> QRect:
        return QRect(
            self.MARGIN,
            self.LABEL_H,
            max(0, self.width() - 2 * self.MARGIN),
            self.TIMELINE_H,
        )

    def _ms_to_x(self, ms: int) -> int:
        rect = self._timeline_rect()
        if self.track.duration_ms <= 0:
            return rect.left()
        return int(rect.left() + (ms / self.track.duration_ms) * rect.width())

    def _x_to_ms(self, x: int) -> int:
        rect = self._timeline_rect()
        if rect.width() <= 0 or self.track.duration_ms <= 0:
            return 0
        t = (x - rect.left()) / rect.width()
        return max(0, min(self.track.duration_ms, int(t * self.track.duration_ms)))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Active indicator dot + track label
        label_color = QColor(0, 103, 192) if self._is_active else QColor(110, 110, 110)
        painter.setPen(label_color)
        painter.drawText(
            QRect(self.MARGIN, 0, self.width() - 2 * self.MARGIN, self.LABEL_H),
            Qt.AlignmentFlag.AlignVCenter,
            ("●  " if self._is_active else "○  ") + self.track.display_name,
        )

        rect = self._timeline_rect()

        # Track background
        bg = QColor(245, 245, 245) if not self._is_active else QColor(238, 244, 252)
        painter.fillRect(rect, bg)

        # Thumbnails — fixed native aspect, centered on their time position.
        # Longer videos get more thumbnails (decided in extractor).
        if self.track.thumbnails and self.track.duration_ms > 0:
            n = len(self.track.thumbnails)
            # Aspect-preserving width at the track's timeline height
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
            painter.setPen(QColor(140, 140, 140))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                tr("veditor.track.no_source") if self.track.source_path is None
                else tr("veditor.track.loading"),
            )

        # Speed segments overlay
        for seg in self.track.speed_segments:
            x1 = self._ms_to_x(seg.start_ms)
            x2 = self._ms_to_x(seg.end_ms)
            color = self._color_for_speed(seg.speed)
            painter.fillRect(
                x1, rect.top(), max(1, x2 - x1), rect.height(), color
            )
            if x2 - x1 > 32:
                painter.setPen(QColor(20, 20, 20))
                painter.drawText(
                    QRect(x1, rect.top(), x2 - x1, rect.height()),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{seg.speed:g}x",
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

        # Selection
        sel_start = self.track.selection_start_ms
        sel_end = self.track.selection_end_ms
        if sel_start >= 0 and sel_end > sel_start:
            sx1 = self._ms_to_x(sel_start)
            sx2 = self._ms_to_x(sel_end)
            painter.fillRect(
                sx1, rect.top(), max(1, sx2 - sx1), rect.height(),
                QColor(0, 103, 192, 70),
            )
            pen = QPen(QColor(0, 103, 192))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(sx1, rect.top(), max(1, sx2 - sx1), rect.height())

        # Active track border
        if self._is_active:
            pen = QPen(QColor(0, 103, 192))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            # Playhead
            pen = QPen(QColor(210, 30, 30))
            pen.setWidth(2)
            painter.setPen(pen)
            px = self._ms_to_x(self._position_ms)
            painter.drawLine(px, rect.top() - 2, px, rect.bottom() + 2)

    @staticmethod
    def _color_for_speed(speed: float) -> QColor:
        if speed < 1.0:
            t = min(1.0, (1.0 - speed) / 0.75)
            return QColor(int(120 + 80 * t), int(180 - 80 * t), 255, 130)
        if speed > 1.0:
            t = min(1.0, (speed - 1.0) / 15.0)
            return QColor(255, int(180 - 130 * t), int(120 - 100 * t), 130)
        return QColor(150, 150, 150, 100)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.clicked.emit(self.track.id)
        if self.track.duration_ms <= 0:
            return
        rect = self._timeline_rect()
        if not rect.contains(event.position().toPoint()):
            return
        ms = self._x_to_ms(event.position().toPoint().x())
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._dragging_selection = True
            self._drag_start_ms = ms
            self.track.selection_start_ms = ms
            self.track.selection_end_ms = ms
            self.update()
        else:
            self._dragging_playhead = True
            self.position_requested.emit(self.track.id, ms)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.track.duration_ms <= 0:
            return
        ms = self._x_to_ms(event.position().toPoint().x())
        if self._dragging_selection:
            self.track.selection_start_ms = min(self._drag_start_ms, ms)
            self.track.selection_end_ms = max(self._drag_start_ms, ms)
            self.update()
        elif self._dragging_playhead:
            self.position_requested.emit(self.track.id, ms)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
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
        self.context_menu.emit(self.track.id, self.mapToGlobal(local_pos))


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

        self.setObjectName("EditorRoot")
        self.setWindowTitle(tr("veditor.title"))
        self.resize(1180, 780)

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
        self.zoom_label.setFixedWidth(70)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setStyleSheet("color: #5a5a5a; font-family: Consolas;")

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setObjectName("ToolButton")
        self.zoom_in_btn.setFixedWidth(32)
        self.zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_in_btn.clicked.connect(lambda: self._change_zoom(1.5))

        self.zoom_fit_btn = QPushButton(tr("veditor.btn.zoom_fit"))
        self.zoom_fit_btn.setObjectName("ToolButton")
        self.zoom_fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_fit_btn.clicked.connect(self._zoom_fit)

        toolbar.addWidget(self.add_track_btn)
        toolbar.addWidget(self.del_track_btn)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.reset_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.zoom_out_btn)
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_in_btn)
        toolbar.addWidget(self.zoom_fit_btn)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.export_btn)
        root.addLayout(toolbar)

        # --- Preview (QLabel displaying decoded frames from SimpleVideoPlayer) ---
        preview_host = QWidget()
        preview_host.setObjectName("PreviewHost")
        preview_host.setStyleSheet(
            "QWidget#PreviewHost { background-color: #0a0a0a; }"
        )
        preview_host.setFixedHeight(280)
        preview_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        host_layout = QVBoxLayout(preview_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("color: #999;")
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

        # --- Paint hint under preview ---
        self._paint_hint_label = QLabel(tr("paint.hint"))
        self._paint_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._paint_hint_label.setStyleSheet(
            "color: #6a6a6a; font-size: 11px; padding: 2px;"
        )
        root.addWidget(self._paint_hint_label)

        # --- Transport row ---
        transport = QHBoxLayout()
        transport.setSpacing(8)
        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("ToolButton")
        self.play_btn.setFixedWidth(50)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self._toggle_play)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("font-family: Consolas, monospace;")

        self.current_speed_label = QLabel(
            tr("veditor.current_speed", speed="1.0")
        )
        self.current_speed_label.setStyleSheet("color: #0067c0; font-weight: 600;")

        transport.addWidget(self.play_btn)
        transport.addWidget(self.time_label)
        transport.addStretch(1)
        transport.addWidget(self.current_speed_label)
        root.addLayout(transport)

        # --- Tracks container (scrollable vertically) ---
        self._tracks_host = QWidget()
        self._tracks_layout = QVBoxLayout(self._tracks_host)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(6)
        self._tracks_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._tracks_layout.addStretch(1)

        self._tracks_scroll = QScrollArea()
        self._tracks_scroll.setWidgetResizable(True)
        self._tracks_scroll.setWidget(self._tracks_host)
        self._tracks_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._tracks_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tracks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tracks_scroll.setStyleSheet("QScrollArea { background: transparent; }")
        root.addWidget(self._tracks_scroll, stretch=1)

        # --- Selection / speed buttons row ---
        sel_row = QHBoxLayout()
        sel_row.setSpacing(6)
        self.selection_label = QLabel(tr("veditor.no_selection"))
        self.selection_label.setStyleSheet("color: #3a3a3a;")
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
        root.addLayout(sel_row)

        # --- Subtitle panel ---
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
        self._track_rows[track.id] = row
        self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, row)
        self._update_tracks_host_width()

    def _update_tracks_host_width(self) -> None:
        max_w = MIN_TRACK_WIDTH
        for row in self._track_rows.values():
            max_w = max(max_w, row.width())
        self._tracks_host.setMinimumWidth(max_w)

    def _change_zoom(self, factor: float) -> None:
        new_px = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, self._px_per_sec * factor))
        if abs(new_px - self._px_per_sec) < 0.001:
            return
        self._px_per_sec = new_px
        for row in self._track_rows.values():
            row.set_px_per_sec(new_px)
        self.zoom_label.setText(self._format_zoom())
        self._update_tracks_host_width()

    def _zoom_fit(self) -> None:
        if not self._tracks:
            return
        max_dur = max((t.duration_ms for t in self._tracks), default=0)
        if max_dur <= 0:
            return
        viewport_w = self._tracks_scroll.viewport().width()
        if viewport_w <= 50:
            return
        target_px = (viewport_w - 40) / (max_dur / 1000.0)
        target_px = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, target_px))
        self._px_per_sec = target_px
        for row in self._track_rows.values():
            row.set_px_per_sec(target_px)
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
        pix = QPixmap.fromImage(qimg)
        self._preview_pixmap = pix
        self._scale_preview_to_fit()
        self._update_subtitle_overlay(self._player.position())
        # The overlay is a child — bring on top of preview label each frame
        self._drawing_canvas.raise_()
        self._subtitle_overlay.raise_()
        self._drawing_canvas.update()

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
        if obj is self._preview_label:
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._open_paint_dialog()
                    return True
                if event.button() == Qt.MouseButton.RightButton:
                    self._show_preview_context_menu(event.globalPosition().toPoint())
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

        dlg = PaintDialog(
            background_pixmap=self._preview_pixmap,
            initial_strokes=self._strokes,
            time_ms=self._player.position(),
            parent=self,
        )
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._strokes = dlg.result_strokes()
            self._drawing_canvas.update()

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
        self._preview_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_preview_to_fit()
        if self._subtitle_overlay.isVisible():
            self._reposition_subtitle_overlay()
        # Keep drawing canvas covering the preview host
        host = self._preview_host
        self._drawing_canvas.setGeometry(0, 0, host.width(), host.height())

    def _on_position_changed(self, pos: int) -> None:
        # Playhead shows on every track at project time
        for row in self._track_rows.values():
            row.set_position(pos)
        self.time_label.setText(
            f"{_format_ms(pos)} / {_format_ms(self._player.duration())}"
        )
        self._update_subtitle_overlay(pos)
        # Drawings can appear/disappear based on current time
        self._drawing_canvas.update()

        # Report speed at the currently-rendered track
        active_for_render = None
        for t in reversed(self._tracks):
            if t.source_path is None:
                continue
            if pos >= t.duration_ms:
                continue
            if any(c.start_ms <= pos < c.end_ms for c in t.cuts):
                continue
            active_for_render = t
            break
        if active_for_render is None:
            speed = 1.0
        else:
            speed = self._speed_at(active_for_render, pos)
        if speed != self._current_segment_speed:
            self._current_segment_speed = speed
            self.current_speed_label.setText(
                tr("veditor.current_speed", speed=f"{speed:g}")
            )

    def _on_duration_changed(self, dur: int) -> None:
        for row in self._track_rows.values():
            row._recalc_width()
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
