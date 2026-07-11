from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.audio_tracks import AudioClip, probe_audio_duration_ms

__all__ = [
    "NestedSequenceEditorDialog",
    "NestedTimelineCanvas",
    "cut_clip_window",
]


class NestedTimelineCanvas(QWidget):
    """Compact timeline editor used inside NestedSequenceEditorDialog."""

    changed = Signal()
    selection_changed = Signal(str, int, int)

    def __init__(
        self,
        video_tracks: list[list],
        audio_tracks: list[list],
        spine_tracks: list | None = None,
        live2d_tracks: list | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._video_tracks = video_tracks
        self._audio_tracks = audio_tracks
        self._spine_tracks = spine_tracks or []
        self._live2d_tracks = live2d_tracks or []
        self._selected: set[tuple[str, int, int]] = set()
        self._drag_mode: str | None = None
        self._drag_start_x = 0
        self._drag_target: tuple[str, int, int] | None = None
        self._drag_original: dict[tuple[str, int, int], tuple[int, int, int]] = {}
        self._zoom = 1.0
        self._scroll_ms = 0
        self._playhead_ms = 0
        self.setMinimumHeight(220)
        self.setMouseTracking(True)

    def set_tracks(
        self,
        video_tracks: list[list],
        audio_tracks: list[list],
        spine_tracks: list | None = None,
        live2d_tracks: list | None = None,
    ) -> None:
        self._video_tracks = video_tracks
        self._audio_tracks = audio_tracks
        self._spine_tracks = spine_tracks or []
        self._live2d_tracks = live2d_tracks or []
        self._selected = {
            key for key in self._selected if self._clip_for_key(key) is not None
        }
        self.setMinimumHeight(max(220, 48 + len(self._all_tracks()) * 40))
        self.update()

    def set_playhead_ms(self, ms: int) -> None:
        self._playhead_ms = max(0, int(ms))
        self.update()

    def select(self, kind: str, lane: int, index: int) -> None:
        key = (kind, int(lane), int(index))
        if self._clip_for_key(key) is None:
            return
        self._selected = {key}
        self.selection_changed.emit(kind, int(lane), int(index))
        self.update()

    def _all_tracks(self) -> list[tuple[str, int, list]]:
        out: list[tuple[str, int, list]] = []
        for i, track in enumerate(self._video_tracks):
            out.append(("video", i, track))
        for i, track in enumerate(self._audio_tracks):
            out.append(("audio", i, track))
        for i, track in enumerate(self._spine_tracks):
            out.append(("spine", i, getattr(track, "clips", []) or []))
        for i, track in enumerate(self._live2d_tracks):
            out.append(("live2d", i, getattr(track, "clips", []) or []))
        return out

    def _duration_ms(self) -> int:
        latest = 1000
        for kind, _lane, track in self._all_tracks():
            for clip in track:
                latest = max(latest, self._clip_end_ms(kind, clip))
        return latest

    def _left_margin(self) -> int:
        return 72

    def _lane_rect(self, row: int) -> QRect:
        return QRect(self._left_margin(), 28 + row * 40, max(1, self.width() - self._left_margin() - 14), 32)

    def _px_per_ms(self) -> float:
        visible_ms = max(250, int(self._duration_ms() / max(1.0, self._zoom)))
        return max(1.0, self.width() - self._left_margin() - 14) / visible_ms

    def _x_for_ms(self, ms: int) -> int:
        return self._left_margin() + int(round((max(0, int(ms)) - self._scroll_ms) * self._px_per_ms()))

    def _ms_for_x(self, x: int) -> int:
        return max(0, int(round((int(x) - self._left_margin()) / max(self._px_per_ms(), 0.001))) + int(self._scroll_ms))

    def _visible_duration_ms(self) -> int:
        return max(250, int(self._duration_ms() / max(1.0, self._zoom)))

    def _clamp_scroll(self) -> None:
        max_scroll = max(0, self._duration_ms() - self._visible_duration_ms())
        self._scroll_ms = max(0, min(int(self._scroll_ms), int(max_scroll)))

    def _clip_for_key(self, key: tuple[str, int, int]):
        kind, lane, index = key
        if kind == "video":
            tracks = self._video_tracks
            try:
                return tracks[int(lane)][int(index)]
            except Exception:
                return None
        if kind == "audio":
            tracks = self._audio_tracks
            try:
                return tracks[int(lane)][int(index)]
            except Exception:
                return None
        tracks = self._spine_tracks if kind == "spine" else self._live2d_tracks
        try:
            return getattr(tracks[int(lane)], "clips", [])[int(index)]
        except Exception:
            return None

    def _clip_start_ms(self, kind: str, clip) -> int:
        if kind == "audio":
            return int(getattr(clip, "offset_ms", 0))
        if kind in ("spine", "live2d"):
            return int(getattr(clip, "start_ms", 0))
        return int(getattr(clip, "timeline_in_ms", 0))

    def _clip_end_ms(self, kind: str, clip) -> int:
        if kind == "audio":
            return int(getattr(clip, "offset_ms", 0)) + int(getattr(clip, "effective_length_ms", 0))
        if kind in ("spine", "live2d"):
            return int(getattr(clip, "end_ms", 0))
        return int(getattr(clip, "timeline_out_ms", 0))

    def _clip_name(self, clip) -> str:
        sp = getattr(clip, "source_path", None)
        if sp is not None:
            return Path(sp).stem
        model = getattr(clip, "model_path", None)
        if model:
            return Path(model).stem
        skel = getattr(clip, "skel_path", None)
        if skel:
            return Path(skel).stem
        anim = getattr(clip, "anim_name", "")
        if anim:
            return str(anim)
        return getattr(clip, "nested_sequence_name", "") or "Nested"

    def _clip_rect(self, kind: str, row: int, clip) -> QRect:
        lane = self._lane_rect(row)
        x1 = self._x_for_ms(self._clip_start_ms(kind, clip))
        x2 = self._x_for_ms(self._clip_end_ms(kind, clip))
        return QRect(x1, lane.y() + 4, max(6, x2 - x1), lane.height() - 8)

    def _hit_test(self, pos: QPoint) -> tuple[str, int, int, str] | None:
        for row, (kind, lane, track) in enumerate(self._all_tracks()):
            for index in range(len(track) - 1, -1, -1):
                rect = self._clip_rect(kind, row, track[index])
                if not rect.contains(pos):
                    continue
                if pos.x() <= rect.left() + 7:
                    zone = "left"
                elif pos.x() >= rect.right() - 7:
                    zone = "right"
                else:
                    zone = "body"
                return kind, lane, index, zone
        return None

    def _event_pos(self, event) -> QPoint:
        try:
            return event.position().toPoint()
        except Exception:
            return event.pos()

    def _snapshot_selected(self) -> None:
        self._drag_original = {}
        for key in self._selected:
            clip = self._clip_for_key(key)
            if clip is None:
                continue
            kind, _lane, _index = key
            if kind == "audio":
                self._drag_original[key] = (
                    int(getattr(clip, "offset_ms", 0)),
                    int(getattr(clip, "trim_start_ms", 0)),
                    int(getattr(clip, "effective_trim_end_ms", 0)),
                )
            elif kind in ("spine", "live2d"):
                self._drag_original[key] = (
                    int(getattr(clip, "start_ms", 0)),
                    0,
                    int(getattr(clip, "duration_ms", 0)),
                )
            else:
                self._drag_original[key] = (
                    int(getattr(clip, "timeline_in_ms", 0)),
                    int(getattr(clip, "source_in_ms", 0)),
                    int(getattr(clip, "effective_source_out_ms", 0)),
                )

    def _snap_delta(self, anchor: tuple[str, int, int], target_start: int) -> int:
        snap_ms = max(20, int(round(8 / max(self._px_per_ms(), 0.001))))
        kind, lane, _index = anchor
        if kind == "video":
            tracks = self._video_tracks
        elif kind == "audio":
            tracks = self._audio_tracks
        else:
            tracks = self._spine_tracks if kind == "spine" else self._live2d_tracks
        candidates = [0]
        try:
            lane_clips = tracks[lane] if kind in ("video", "audio") else getattr(tracks[lane], "clips", [])
            for ci, clip in enumerate(lane_clips):
                key = (kind, lane, ci)
                if key in self._selected:
                    continue
                candidates.append(self._clip_start_ms(kind, clip))
                candidates.append(self._clip_end_ms(kind, clip))
        except Exception:
            pass
        nearest = min(candidates, key=lambda ms: abs(int(ms) - int(target_start)))
        if abs(int(nearest) - int(target_start)) <= snap_ms:
            return int(nearest) - int(target_start)
        return 0

    def _apply_move(self, raw_delta_ms: int) -> None:
        if not self._drag_original:
            return
        keys = list(self._drag_original.keys())
        min_start = min(start for start, _a, _b in self._drag_original.values())
        delta = max(int(raw_delta_ms), -int(min_start))
        anchor = self._drag_target if self._drag_target in self._drag_original else keys[0]
        if anchor is not None:
            start, _a, _b = self._drag_original[anchor]
            delta += self._snap_delta(anchor, start + delta)
        for key, (start, src_in, src_out) in self._drag_original.items():
            clip = self._clip_for_key(key)
            if clip is None:
                continue
            kind, _lane, _index = key
            if kind == "audio":
                clip.offset_ms = max(0, int(start + delta))
            elif kind in ("spine", "live2d"):
                clip.start_ms = max(0, int(start + delta))
            else:
                clip.timeline_in_ms = max(0, int(start + delta))

    def _apply_resize(self, raw_delta_ms: int) -> None:
        key = self._drag_target
        if key is None or key not in self._drag_original:
            return
        clip = self._clip_for_key(key)
        if clip is None:
            return
        kind, _lane, _index = key
        start, src_in, src_out = self._drag_original[key]
        delta = int(raw_delta_ms)
        if self._drag_mode == "left":
            length = max(1, int(src_out) - int(src_in))
            target_start = max(0, min(int(start) + delta, int(start) + length - 1))
            actual_delta = int(target_start) - int(start)
            if kind == "audio":
                clip.trim_start_ms = max(0, min(int(src_out) - 1, int(src_in) + actual_delta))
                clip.offset_ms = max(0, int(start) + int(clip.trim_start_ms) - int(src_in))
            elif kind in ("spine", "live2d"):
                old_duration = max(1, int(src_out))
                target_start = max(0, min(int(start) + delta, int(start) + old_duration - 1))
                actual_delta = int(target_start) - int(start)
                clip.start_ms = target_start
                clip.duration_ms = max(1, old_duration - actual_delta)
            else:
                clip.source_in_ms = max(0, min(int(src_out) - 1, int(src_in) + actual_delta))
                clip.timeline_in_ms = max(0, int(start) + int(clip.source_in_ms) - int(src_in))
        elif self._drag_mode == "right":
            if kind == "audio":
                max_out = int(getattr(clip, "duration_ms", 0) or src_out)
                clip.trim_end_ms = max(int(src_in) + 1, min(max_out, int(src_out) + delta))
            elif kind in ("spine", "live2d"):
                clip.duration_ms = max(1, int(src_out) + delta)
            else:
                max_out = int(getattr(clip, "source_duration_ms", 0) or src_out)
                clip.source_out_ms = max(int(src_in) + 1, min(max_out, int(src_out) + delta))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        hit = self._hit_test(self._event_pos(event))
        if hit is None:
            self._selected.clear()
            self.update()
            return
        kind, lane, index, zone = hit
        key = (kind, lane, index)
        mods = event.modifiers()
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if key in self._selected:
                self._selected.remove(key)
            else:
                self._selected.add(key)
        elif key not in self._selected:
            self._selected = {key}
        self._drag_mode = zone
        self._drag_target = key
        self._drag_start_x = self._event_pos(event).x()
        self._snapshot_selected()
        self.selection_changed.emit(kind, lane, index)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode is None:
            hit = self._hit_test(self._event_pos(event))
            if hit is None:
                self.unsetCursor()
            elif hit[3] in ("left", "right"):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        delta_px = self._event_pos(event).x() - self._drag_start_x
        delta_ms = int(round(delta_px / max(self._px_per_ms(), 0.001) / 10.0) * 10)
        if self._drag_mode == "body":
            self._apply_move(delta_ms)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self._apply_resize(delta_ms)
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.changed.emit()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode is not None:
            self._drag_mode = None
            self._drag_target = None
            self._drag_original = {}
            self.changed.emit()
        self.unsetCursor()
        self.update()

    def wheelEvent(self, event) -> None:
        delta = 0
        try:
            delta = int(event.angleDelta().y())
        except Exception:
            pass
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ShiftModifier:
            step = max(50, self._visible_duration_ms() // 12)
            self._scroll_ms += -step if delta > 0 else step
            self._clamp_scroll()
            self.update()
            return
        old_ms = self._ms_for_x(self._event_pos(event).x())
        if delta > 0:
            self._zoom = min(16.0, self._zoom * 1.18)
        elif delta < 0:
            self._zoom = max(1.0, self._zoom / 1.18)
        new_ms = self._ms_for_x(self._event_pos(event).x())
        self._scroll_ms += old_ms - new_ms
        self._clamp_scroll()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#11131c"))
        painter.setPen(QColor("#76798a"))
        painter.drawText(10, 18, f"{self._duration_ms() / 1000.0:.1f}s  x{self._zoom:.1f}")
        start_tick = int(self._scroll_ms // 1000 * 1000)
        end_tick = int(self._scroll_ms + self._visible_duration_ms() + 1000)
        for ms in range(start_tick, end_tick + 1, 1000):
            x = self._x_for_ms(ms)
            if x < self._left_margin() or x > self.width():
                continue
            painter.setPen(QColor("#252938"))
            painter.drawLine(x, 24, x, self.height() - 8)
            painter.setPen(QColor("#777b8c"))
            painter.drawText(x + 4, 18, f"{ms // 1000}s")
        for row, (kind, lane, track) in enumerate(self._all_tracks()):
            lane_rect = self._lane_rect(row)
            painter.fillRect(QRect(0, lane_rect.y(), self.width(), lane_rect.height()), QColor("#171a24"))
            painter.setPen(QColor("#8b8fa0"))
            prefix = {"video": "V", "audio": "A", "spine": "S", "live2d": "L"}.get(kind, "?")
            painter.drawText(12, lane_rect.y() + 21, f"{prefix}{lane + 1}")
            painter.setPen(QColor("#2c3142"))
            painter.drawRect(lane_rect)
            for index, clip in enumerate(track):
                rect = self._clip_rect(kind, row, clip)
                selected = (kind, lane, index) in self._selected
                fill = {
                    "video": QColor("#4f6df5"),
                    "audio": QColor("#2aa878"),
                    "spine": QColor("#b15cff"),
                    "live2d": QColor("#e28c3a"),
                }.get(kind, QColor("#777777"))
                if selected:
                    fill = fill.lighter(125)
                painter.fillRect(rect, fill)
                painter.setPen(QColor("#f7f8ff") if selected else QColor("#cfd4e6"))
                painter.drawRect(rect)
                painter.setPen(QColor("#ffffff"))
                text = self._clip_name(clip)
                painter.drawText(rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
                painter.setPen(QColor("#ffffff"))
                painter.drawLine(rect.left() + 4, rect.top() + 5, rect.left() + 4, rect.bottom() - 5)
                painter.drawLine(rect.right() - 4, rect.top() + 5, rect.right() - 4, rect.bottom() - 5)
        play_x = self._x_for_ms(self._playhead_ms)
        if self._left_margin() <= play_x <= self.width():
            painter.setPen(QPen(QColor("#f2d35e"), 2))
            painter.drawLine(play_x, 24, play_x, self.height() - 8)
        if not self._all_tracks():
            painter.setPen(QColor("#8b8fa0"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No nested media")
        painter.end()


class NestedSequenceEditorDialog(QDialog):
    """Small internal editor for a nested sequence clip.

    It edits child video lanes and nested audio lanes without launching
    another full VideoEditorWindow recursively.
    """

    def __init__(self, clip, parent=None) -> None:
        super().__init__(parent)
        import copy
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QHeaderView,
            QTableWidget,
            QTableWidgetItem,
        )

        self._clip = clip
        self._tracks = copy.deepcopy(
            getattr(clip, "nested_child_tracks", None)
            or ([list(getattr(clip, "nested_child_clips", []) or [])])
        )
        self._tracks = [list(t) for t in self._tracks if t]
        if not self._tracks:
            self._tracks = [[]]
        self._audio_tracks = copy.deepcopy(
            getattr(clip, "nested_audio_tracks", None) or []
        )
        self._audio_tracks = [list(t) for t in self._audio_tracks if t]
        self._spine_tracks = copy.deepcopy(
            getattr(clip, "nested_spine_actor_tracks", None) or []
        )
        self._live2d_tracks = copy.deepcopy(
            getattr(clip, "nested_live2d_actor_tracks", None) or []
        )
        self._active_media = "video"
        self._timeline_selection: tuple[str, int, int] | None = None
        self._refreshing = False

        self.setWindowTitle(getattr(clip, "nested_sequence_name", "") or "Nested sequence")
        self.resize(980, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        top = QHBoxLayout()
        self._name_label = QLabel(getattr(clip, "nested_sequence_name", "") or "Nested sequence")
        self._name_label.setStyleSheet("font-weight:700; color:#e8e8f2;")
        top.addWidget(self._name_label)
        top.addStretch(1)
        self._add_track_btn = QPushButton("Add video track")
        self._add_audio_track_btn = QPushButton("Add audio track")
        self._add_media_btn = QPushButton("Add video")
        self._add_audio_btn = QPushButton("Add audio")
        self._import_spine_btn = QPushButton("Import Spine")
        self._import_live2d_btn = QPushButton("Import Live2D")
        self._move_up_btn = QPushButton("Move lane up")
        self._move_down_btn = QPushButton("Move lane down")
        self._delete_btn = QPushButton("Delete clip")
        for btn in (
            self._add_track_btn,
            self._add_audio_track_btn,
            self._add_media_btn,
            self._add_audio_btn,
            self._import_spine_btn,
            self._import_live2d_btn,
            self._move_up_btn,
            self._move_down_btn,
            self._delete_btn,
        ):
            btn.setObjectName("ToolButton")
            top.addWidget(btn)
        root.addLayout(top)

        self._timeline = NestedTimelineCanvas(
            self._tracks,
            self._audio_tracks,
            self._spine_tracks,
            self._live2d_tracks,
            self,
        )
        try:
            parent_pos = int(parent._player.position()) if parent is not None and hasattr(parent, "_player") else 0
            self._timeline.set_playhead_ms(parent_pos - int(getattr(clip, "timeline_in_ms", 0)))
        except Exception:
            pass
        root.addWidget(self._timeline, 0)

        video_label = QLabel("Video lanes")
        video_label.setStyleSheet("color:#b9bdcc; font-size:11px; font-weight:700;")
        root.addWidget(video_label)
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Lane", "Source", "Start", "In", "Out"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table, 1)

        audio_label = QLabel("Audio lanes")
        audio_label.setStyleSheet("color:#b9bdcc; font-size:11px; font-weight:700;")
        root.addWidget(audio_label)
        self._audio_table = QTableWidget(0, 5)
        self._audio_table.setHorizontalHeaderLabels(["Lane", "Source", "Start", "In", "Out"])
        self._audio_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._audio_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._audio_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._audio_table.verticalHeader().setVisible(False)
        root.addWidget(self._audio_table, 1)

        hint = QLabel("Drag clips to move, drag edges to trim. Mouse wheel zooms; Shift+wheel scrolls. Start/In/Out values are milliseconds.")
        hint.setStyleSheet("color:#9a9aaa; font-size:11px;")
        root.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._add_track_btn.clicked.connect(self._add_track)
        self._add_audio_track_btn.clicked.connect(self._add_audio_track)
        self._add_media_btn.clicked.connect(self._add_media)
        self._add_audio_btn.clicked.connect(self._add_audio)
        self._import_spine_btn.clicked.connect(self._import_spine_from_timeline)
        self._import_live2d_btn.clicked.connect(self._import_live2d_from_timeline)
        self._move_up_btn.clicked.connect(lambda: self._move_selected_clip_lane(-1))
        self._move_down_btn.clicked.connect(lambda: self._move_selected_clip_lane(+1))
        self._delete_btn.clicked.connect(self._delete_selected_clip)
        self._timeline.changed.connect(self._on_timeline_changed)
        self._timeline.selection_changed.connect(self._on_timeline_selected)
        self._table.itemSelectionChanged.connect(self._on_video_table_selected)
        self._audio_table.itemSelectionChanged.connect(self._on_audio_table_selected)
        self._refresh_table()

    def _probe_duration_ms(self, path: Path) -> int:
        try:
            import cv2
            cap = cv2.VideoCapture(str(path))
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            cap.release()
            if fps > 0 and frames > 0:
                return int(frames / fps * 1000)
        except Exception:
            pass
        return 0

    def _next_child_id(self) -> int:
        return max(
            (
                int(getattr(c, "id", 0) or 0)
                for track in self._tracks
                for c in track
            ),
            default=0,
        ) + 1

    def _next_audio_child_id(self) -> int:
        return max(
            (
                int(getattr(c, "id", 0) or 0)
                for track in self._audio_tracks
                for c in track
            ),
            default=0,
        ) + 1

    def _selected_index(self) -> tuple[int, int] | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple) or len(data) != 2:
            return None
        return int(data[0]), int(data[1])

    def _selected_audio_index(self) -> tuple[int, int] | None:
        row = self._audio_table.currentRow()
        if row < 0:
            return None
        item = self._audio_table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple) or len(data) != 2:
            return None
        return int(data[0]), int(data[1])

    def _selected_any(self) -> tuple[str, int, int] | None:
        if self._active_media in ("spine", "live2d") and self._timeline_selection is not None:
            return self._timeline_selection
        if self._active_media == "audio":
            idx = self._selected_audio_index()
            if idx is not None:
                return "audio", idx[0], idx[1]
        idx = self._selected_index()
        if idx is not None:
            return "video", idx[0], idx[1]
        idx = self._selected_audio_index()
        if idx is not None:
            return "audio", idx[0], idx[1]
        return None

    def _spin(self, value: int, maximum: int = 24 * 60 * 60 * 1000) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, max(0, int(maximum)))
        spin.setValue(max(0, int(value)))
        spin.setSingleStep(100)
        return spin

    def _select_table_row(self, table, lane: int, index: int) -> None:
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == (lane, index):
                table.selectRow(row)
                return

    def _refresh_table(self, *, sync_canvas: bool = True) -> None:
        from PySide6.QtWidgets import QTableWidgetItem

        current_video = self._selected_index()
        current_audio = self._selected_audio_index()
        self._refreshing = True
        self._table.setRowCount(0)
        for ti, track in enumerate(self._tracks):
            for ci, child in enumerate(track):
                row = self._table.rowCount()
                self._table.insertRow(row)
                lane_item = QTableWidgetItem(str(ti + 1))
                lane_item.setData(Qt.ItemDataRole.UserRole, (ti, ci))
                self._table.setItem(row, 0, lane_item)
                source = getattr(child, "source_path", None)
                self._table.setItem(row, 1, QTableWidgetItem(Path(source).name if source else "Nested"))
                self._table.setCellWidget(row, 2, self._spin(int(getattr(child, "timeline_in_ms", 0))))
                self._table.setCellWidget(row, 3, self._spin(int(getattr(child, "source_in_ms", 0))))
                max_out = int(getattr(child, "source_duration_ms", 0) or 24 * 60 * 60 * 1000)
                self._table.setCellWidget(
                    row,
                    4,
                    self._spin(int(getattr(child, "effective_source_out_ms", 0)), max_out),
                )
        self._audio_table.setRowCount(0)
        for ti, track in enumerate(self._audio_tracks):
            for ci, child in enumerate(track):
                row = self._audio_table.rowCount()
                self._audio_table.insertRow(row)
                lane_item = QTableWidgetItem(str(ti + 1))
                lane_item.setData(Qt.ItemDataRole.UserRole, (ti, ci))
                self._audio_table.setItem(row, 0, lane_item)
                source = getattr(child, "source_path", None)
                self._audio_table.setItem(row, 1, QTableWidgetItem(Path(source).name if source else "Audio"))
                self._audio_table.setCellWidget(row, 2, self._spin(int(getattr(child, "offset_ms", 0))))
                self._audio_table.setCellWidget(row, 3, self._spin(int(getattr(child, "trim_start_ms", 0))))
                max_out = int(getattr(child, "duration_ms", 0) or 24 * 60 * 60 * 1000)
                self._audio_table.setCellWidget(
                    row,
                    4,
                    self._spin(int(getattr(child, "effective_trim_end_ms", 0)), max_out),
                )
        if current_video is not None:
            self._select_table_row(self._table, *current_video)
        if current_audio is not None:
            self._select_table_row(self._audio_table, *current_audio)
        if self._table.rowCount() > 0 and self._table.currentRow() < 0 and self._active_media == "video":
            self._table.selectRow(0)
        if self._audio_table.rowCount() > 0 and self._audio_table.currentRow() < 0 and self._active_media == "audio":
            self._audio_table.selectRow(0)
        self._refreshing = False
        if sync_canvas:
            self._timeline.set_tracks(
                self._tracks,
                self._audio_tracks,
                self._spine_tracks,
                self._live2d_tracks,
            )

    def _write_table_values(self) -> None:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is None:
                continue
            ti, ci = item.data(Qt.ItemDataRole.UserRole)
            try:
                child = self._tracks[int(ti)][int(ci)]
            except Exception:
                continue
            start = self._table.cellWidget(row, 2)
            src_in = self._table.cellWidget(row, 3)
            src_out = self._table.cellWidget(row, 4)
            if isinstance(start, QSpinBox):
                child.timeline_in_ms = int(start.value())
            if isinstance(src_in, QSpinBox):
                child.source_in_ms = int(src_in.value())
            if isinstance(src_out, QSpinBox):
                child.source_out_ms = max(int(child.source_in_ms) + 1, int(src_out.value()))
        for row in range(self._audio_table.rowCount()):
            item = self._audio_table.item(row, 0)
            if item is None:
                continue
            ti, ci = item.data(Qt.ItemDataRole.UserRole)
            try:
                child = self._audio_tracks[int(ti)][int(ci)]
            except Exception:
                continue
            start = self._audio_table.cellWidget(row, 2)
            src_in = self._audio_table.cellWidget(row, 3)
            src_out = self._audio_table.cellWidget(row, 4)
            if isinstance(start, QSpinBox):
                child.offset_ms = int(start.value())
            if isinstance(src_in, QSpinBox):
                child.trim_start_ms = int(src_in.value())
            if isinstance(src_out, QSpinBox):
                child.trim_end_ms = max(int(child.trim_start_ms) + 1, int(src_out.value()))

    def _on_timeline_changed(self) -> None:
        self._refresh_table(sync_canvas=False)

    def _on_timeline_selected(self, kind: str, lane: int, index: int) -> None:
        self._active_media = kind
        self._timeline_selection = (kind, lane, index)
        self._refreshing = True
        if kind == "audio":
            self._table.clearSelection()
            self._select_table_row(self._audio_table, lane, index)
        elif kind == "video":
            self._audio_table.clearSelection()
            self._select_table_row(self._table, lane, index)
        else:
            self._table.clearSelection()
            self._audio_table.clearSelection()
        self._refreshing = False

    def _on_video_table_selected(self) -> None:
        if self._refreshing:
            return
        idx = self._selected_index()
        if idx is None:
            return
        self._active_media = "video"
        self._timeline_selection = ("video", idx[0], idx[1])
        self._audio_table.clearSelection()
        self._timeline.select("video", idx[0], idx[1])

    def _on_audio_table_selected(self) -> None:
        if self._refreshing:
            return
        idx = self._selected_audio_index()
        if idx is None:
            return
        self._active_media = "audio"
        self._timeline_selection = ("audio", idx[0], idx[1])
        self._table.clearSelection()
        self._timeline.select("audio", idx[0], idx[1])

    def _add_track(self) -> None:
        self._write_table_values()
        self._tracks.append([])
        self._refresh_table()

    def _add_audio_track(self) -> None:
        self._write_table_values()
        self._audio_tracks.append([])
        self._active_media = "audio"
        self._refresh_table()

    def _add_media(self) -> None:
        self._write_table_values()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Add nested media",
            "",
            "Video files (*.mp4 *.mov *.mkv *.webm *.avi);;All files (*.*)",
        )
        if not path:
            return
        src = Path(path)
        duration = self._probe_duration_ms(src)
        if duration <= 0:
            duration = 1000
        from app.timeline_model import VideoClip
        child = VideoClip(
            id=self._next_child_id(),
            source_path=src,
            source_duration_ms=duration,
            timeline_in_ms=0,
            source_in_ms=0,
            source_out_ms=duration,
        )
        idx = self._selected_index()
        lane = idx[0] if idx is not None else max(0, len(self._tracks) - 1)
        while lane >= len(self._tracks):
            self._tracks.append([])
        self._tracks[lane].append(child)
        self._active_media = "video"
        self._refresh_table()
        self._timeline.select("video", lane, len(self._tracks[lane]) - 1)

    def _add_audio(self) -> None:
        self._write_table_values()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Add nested audio",
            "",
            "Audio files (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus);;Video files (*.mp4 *.mov *.mkv *.webm *.avi);;All files (*.*)",
        )
        if not path:
            return
        src = Path(path)
        try:
            duration = probe_audio_duration_ms(src)
        except Exception:
            duration = 0
        if duration <= 0:
            duration = 1000
        child = AudioClip(
            id=self._next_audio_child_id(),
            source_path=src,
            duration_ms=duration,
            offset_ms=0,
            trim_start_ms=0,
            trim_end_ms=duration,
        )
        idx = self._selected_audio_index()
        lane = idx[0] if idx is not None else max(0, len(self._audio_tracks) - 1)
        if not self._audio_tracks:
            self._audio_tracks.append([])
            lane = 0
        while lane >= len(self._audio_tracks):
            self._audio_tracks.append([])
        self._audio_tracks[lane].append(child)
        self._active_media = "audio"
        self._refresh_table()
        self._timeline.select("audio", lane, len(self._audio_tracks[lane]) - 1)

    def _import_actor_tracks_from_timeline(self, kind: str) -> None:
        import copy
        parent = self.parent()
        source_tracks = (
            getattr(parent, "_spine_actor_tracks", [])
            if kind == "spine"
            else getattr(parent, "_live2d_actor_tracks", [])
        )
        if not source_tracks:
            QMessageBox.information(self, "Nested sequence", f"No {kind} actor tracks on the main timeline.")
            return
        parent_start = int(getattr(self._clip, "timeline_in_ms", 0) or 0)
        parent_end = parent_start + max(1, int(getattr(self._clip, "effective_length_ms", 0) or getattr(self._clip, "source_duration_ms", 0) or 1))
        imported = []
        for track in source_tracks:
            new_track = copy.deepcopy(track)
            new_track.clips = []
            for actor_clip in getattr(track, "clips", []) or []:
                start = int(getattr(actor_clip, "start_ms", 0))
                end = int(getattr(actor_clip, "end_ms", 0))
                if end <= parent_start or start >= parent_end:
                    continue
                c = copy.deepcopy(actor_clip)
                c.start_ms = max(0, start - parent_start)
                c.duration_ms = max(1, min(end, parent_end) - max(start, parent_start))
                new_track.clips.append(c)
            if new_track.clips:
                imported.append(new_track)
        if not imported:
            QMessageBox.information(self, "Nested sequence", f"No overlapping {kind} actor clips in this parent clip.")
            return
        if kind == "spine":
            self._spine_tracks = imported
        else:
            self._live2d_tracks = imported
        self._active_media = kind
        self._refresh_table()

    def _import_spine_from_timeline(self) -> None:
        self._import_actor_tracks_from_timeline("spine")

    def _import_live2d_from_timeline(self) -> None:
        self._import_actor_tracks_from_timeline("live2d")

    def _move_selected_clip_lane(self, delta: int) -> None:
        self._write_table_values()
        idx = self._selected_any()
        if idx is None:
            return
        kind, ti, ci = idx
        if kind == "audio":
            tracks = self._audio_tracks
            lane_clips = lambda t: t
        elif kind == "video":
            tracks = self._tracks
            lane_clips = lambda t: t
        else:
            tracks = self._spine_tracks if kind == "spine" else self._live2d_tracks
            lane_clips = lambda t: getattr(t, "clips", [])
        if not tracks:
            return
        new_ti = max(0, min(len(tracks) - 1, ti + int(delta)))
        if new_ti == ti:
            return
        child = lane_clips(tracks[ti]).pop(ci)
        lane_clips(tracks[new_ti]).append(child)
        self._refresh_table()
        self._timeline.select(kind, new_ti, len(lane_clips(tracks[new_ti])) - 1)

    def _delete_selected_clip(self) -> None:
        self._write_table_values()
        idx = self._selected_any()
        if idx is None:
            return
        kind, ti, ci = idx
        if kind == "audio":
            tracks = self._audio_tracks
            lane_clips = lambda t: t
        elif kind == "video":
            tracks = self._tracks
            lane_clips = lambda t: t
        else:
            tracks = self._spine_tracks if kind == "spine" else self._live2d_tracks
            lane_clips = lambda t: getattr(t, "clips", [])
        try:
            lane_clips(tracks[ti]).pop(ci)
        except Exception:
            return
        self._refresh_table()

    def accept(self) -> None:
        self._write_table_values()
        self._tracks = [track for track in self._tracks if track]
        self._audio_tracks = [track for track in self._audio_tracks if track]
        self._spine_tracks = [
            track for track in self._spine_tracks
            if getattr(track, "clips", None)
        ]
        self._live2d_tracks = [
            track for track in self._live2d_tracks
            if getattr(track, "clips", None)
        ]
        if not self._tracks and not self._audio_tracks and not self._spine_tracks and not self._live2d_tracks:
            QMessageBox.warning(self, "Nested sequence", "Nested sequence needs at least one clip.")
            return
        video_duration_ms = max(
            (int(c.timeline_out_ms) for track in self._tracks for c in track),
            default=0,
        )
        audio_duration_ms = max(
            (
                int(getattr(c, "offset_ms", 0)) + int(getattr(c, "effective_length_ms", 0))
                for track in self._audio_tracks
                for c in track
            ),
            default=0,
        )
        spine_duration_ms = max(
            (
                int(getattr(c, "end_ms", 0))
                for track in self._spine_tracks
                for c in getattr(track, "clips", []) or []
            ),
            default=0,
        )
        live2d_duration_ms = max(
            (
                int(getattr(c, "end_ms", 0))
                for track in self._live2d_tracks
                for c in getattr(track, "clips", []) or []
            ),
            default=0,
        )
        duration_ms = max(video_duration_ms, audio_duration_ms, spine_duration_ms, live2d_duration_ms)
        self._clip.nested_child_tracks = self._tracks
        self._clip.nested_child_clips = list(self._tracks[0]) if self._tracks else []
        self._clip.nested_audio_tracks = self._audio_tracks
        self._clip.nested_spine_actor_tracks = self._spine_tracks
        self._clip.nested_live2d_actor_tracks = self._live2d_tracks
        self._clip.source_duration_ms = duration_ms
        self._clip.source_in_ms = 0
        self._clip.source_out_ms = duration_ms
        super().accept()


def cut_clip_window(
    clips: list, cut_start_source_ms: int, cut_end_source_ms: int,
    track_offset_ms: int,
):
    """Pure clip-list mutation for Phase 1.5d Step C: drop the source
    window ``[cut_start_source_ms, cut_end_source_ms)`` from every
    clip in ``clips`` (interpreted as track-local source ms ??the same
    coordinate system ``track.selection_*_ms`` uses today). Each clip
    contributes 0 / 1 / 2 surviving pieces. Returns a new list sorted
    by ``timeline_in_ms``; does not mutate the input.

    Extracted so the editor's ``_cut_selection_in_track`` is a thin
    wrapper that handles only the GUI side (selection state, repaint,
    player refresh) and the clip math is unit-testable headless."""
    from app.frame_repair import frame_repairs_for_source_window
    from app.timeline_model import VideoClip
    s = int(cut_start_source_ms)
    e = int(cut_end_source_ms)
    out: list = []
    for clip in clips:
        cs = clip.source_in_ms
        ce = clip.effective_source_out_ms
        if ce <= s or cs >= e:
            out.append(clip)
            continue
        if cs < s:
            left_end = min(ce, s)
            out.append(VideoClip(
                id=clip.id,
                source_path=clip.source_path,
                source_duration_ms=clip.source_duration_ms,
                timeline_in_ms=clip.timeline_in_ms,
                source_in_ms=cs,
                source_out_ms=left_end,
                speed_segments=list(clip.speed_segments),
                fades=[f for f in clip.fades if f.start_ms < left_end],
                zoom_actors=[
                    z for z in clip.zoom_actors if z.start_ms < left_end
                ],
                typography_actors=[
                    a for a in clip.typography_actors
                    if getattr(a, "start_ms", 0) < left_end
                ],
                frame_repairs=frame_repairs_for_source_window(
                    getattr(clip, "frame_repairs", []) or [],
                    cs,
                    left_end,
                ),
                node_graph=clip.node_graph,
            ))
        if ce > e:
            right_start = max(cs, e)
            out.append(VideoClip(
                id=clip.id + 1,
                source_path=clip.source_path,
                source_duration_ms=clip.source_duration_ms,
                timeline_in_ms=int(track_offset_ms) + right_start,
                source_in_ms=right_start,
                source_out_ms=ce,
                speed_segments=list(clip.speed_segments),
                fades=[f for f in clip.fades if f.end_ms > right_start],
                zoom_actors=[
                    z for z in clip.zoom_actors if z.end_ms > right_start
                ],
                typography_actors=[
                    a for a in clip.typography_actors
                    if getattr(a, "end_ms", 0) > right_start
                ],
                frame_repairs=frame_repairs_for_source_window(
                    getattr(clip, "frame_repairs", []) or [],
                    right_start,
                    ce,
                ),
                node_graph=clip.node_graph,
            ))
    out.sort(key=lambda c: c.timeline_in_ms)
    return out
