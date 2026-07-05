from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import QMenu, QSizePolicy, QWidget

from app.effect_cards import (
    FADE_MIME_TYPE,
    SPEED_MIME_TYPE,
    ZOOM_MIME_TYPE,
    FadeCard,
    SpeedCard,
    ZoomCard,
)
from app.i18n import tr
from app.media_asset_routing import (
    ar_pbr_paths_from_mime as _shared_ar_pbr_paths_from_mime,
    mmd_paths_from_mime as _shared_mmd_paths_from_mime,
    performance_source_paths_from_mime as _shared_performance_source_paths_from_mime,
    timeline_media_paths_from_mime as _shared_timeline_media_paths_from_mime,
)
from app.qt_pixmap_painting import draw_pixmap_cover as _draw_pixmap_cover
from app.studio_theme import (
    STUDIO_ACTION,
    STUDIO_ACTION_EDGE,
    STUDIO_ACTION_HI,
    STUDIO_CUT,
    paint_scissors_marker,
    paint_studio_clip_block,
    paint_studio_clip_label,
    paint_studio_playhead,
    paint_studio_zoom_block,
    paint_timeline_burst,
)
from app.style import COLOR_ACCENT_ORANGE
from app.timeline_cursor import _timeline_tool_cursor
from app.timeline_drop_guides import (
    drop_guide_detail_for_mime as _shared_drop_guide_detail_for_mime,
    drop_guide_segments_for_mime as _shared_drop_guide_segments_for_mime,
    drop_guide_text as _shared_drop_guide_text,
    drop_guide_width_for_mime as _shared_drop_guide_width_for_mime,
    effect_preset_drag_label as _shared_effect_preset_drag_label,
)
from app.timeline_drop_payloads import (
    editor_preset_from_mime as _drop_editor_preset_from_mime,
    effect_preset_from_mime as _drop_effect_preset_from_mime,
    fade_duration_from_mime as _drop_fade_duration_from_mime,
    speed_payload_from_mime as _drop_speed_payload_from_mime,
    text_clip_duration_from_mime as _drop_text_clip_duration_from_mime,
    title_preset_from_mime as _drop_title_preset_from_mime,
    transition_payload_from_mime as _drop_transition_payload_from_mime,
    zoom_duration_from_mime as _drop_zoom_duration_from_mime,
)
from app.timeline_model import FadeSegment, SpeedSegment, ZoomActor
from app.timeline_striped_host import StripedHost
from app.typography import TEXT_CLIP_MIME, TextClip
from app.video_editor_preset_cards import (
    EDITOR_PRESET_MIME_TYPE,
    EFFECT_PRESET_MIME_TYPE,
    TITLE_PRESET_MIME_TYPE,
    TRANSITION_MIME_TYPE,
)
from app.video_track_legacy import VideoTrack


TRACK_HEIGHT = 44
TRACK_V_PADDING = 2
DEFAULT_PX_PER_SEC = 52.0
MIN_PX_PER_SEC = 4.0
MAX_PX_PER_SEC = 300.0
MIN_TRACK_WIDTH = 300
_UX_EVENT_LOG_NAME = "ux_events.jsonl"


class _AntsOwnerProxy:
    def __eq__(self, other) -> bool:
        module = sys.modules.get("app.video_editor_window")
        owner = getattr(module, "_ANTS_OWNER", "video") if module is not None else "video"
        return owner == other


_ANTS_OWNER = _AntsOwnerProxy()


def _append_ux_event(event: str, **payload) -> None:
    """Best-effort interaction log for hard-to-reproduce editing friction."""
    try:
        from app.paths import runtime_log_dir
        path = runtime_log_dir() / _UX_EVENT_LOG_NAME
        row = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "event": str(event or "event"),
        }
        row.update(payload)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _draw_marching_ants(painter: "QPainter", rect: "QRect", offset: int) -> None:
    """Draw the selected-clip outline."""
    r = rect.adjusted(1, 1, -2, -2)
    if r.width() <= 0 or r.height() <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 0, 0, 104), 2))
    painter.drawRoundedRect(r.adjusted(0, 0, 0, 0), 3, 3)
    painter.setPen(QPen(QColor(226, 230, 236, 118), 1.1))
    painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 2, 2)
    painter.setPen(QPen(QColor(255, 91, 76, 150), 1.2))
    painter.drawLine(r.left() + 5, r.top() + 2, r.right() - 5, r.top() + 2)
    painter.restore()


def _format_speed(p: float) -> str:
    """Format a speed factor as '2x' or '0.5x' for UI labels."""
    if abs(p - round(p)) < 1e-3:
        return f"{int(round(p))}x"
    return f"{p:g}x"


class TrackRow(QWidget):
    """Single horizontal track with label row + timeline row."""

    clicked = Signal(int)  # track_id
    position_requested = Signal(int, int)  # track_id, ms
    selection_changed = Signal(int, int, int)  # track_id, start, end
    context_menu = Signal(int, QPoint)  # track_id, global_pos

    MARGIN = 180
    # Slim header strip ??paints the active dot + track name above the
    # timeline body. Trimmed from 18 ??14 to narrow the visual gap
    # between the subtitle lane and the first track (users were trying
    # to drop clips into the header area and missing).
    LABEL_H = 13
    TIMELINE_H = TRACK_HEIGHT
    FADE_EDGE_GRAB_PX = 6  # resize handle hit area in pixels
    TYPO_EDGE_GRAB_PX = 8
    TYPO_CHIP_H = 22             # height of the typography chip strip
    ZOOM_CHIP_H = 18             # height of the zoom actor strip
    ZOOM_EDGE_GRAB_PX = 8        # left/right edge zone for resize on zoom actor
    ZOOM_MIN_DURATION_MS = 200   # can't shrink below this
    TYPO_MIN_DURATION_MS = 200
    SPEED_EDGE_GRAB_PX = 8
    SPEED_MIN_DURATION_MS = 200
    CLIP_EDGE_GRAB_PX = 8        # clip trim / roll edit handle hit area
    CLIP_MIN_DURATION_MS = 100   # minimum clip duration after trim

    offset_changed = Signal(int, int)  # track_id, new_offset_ms
    drag_committed = Signal(int)       # track_id ??emitted ONLY on mouseRelease
    # Emitted during clip drag so the editor can sync linked audio.
    # Carries (track_id, clip_id, new_timeline_in_ms, delta_ms).
    clip_drag_delta = Signal(int, int, int, int)
    # Incremental project-time delta for selected clips on other tracks.
    cross_track_group_drag_delta = Signal(int, int, int)
    # Option C ??clip-level selection. ``shift_held`` lets the
    # editor decide between "replace selection" and "toggle".
    clip_clicked = Signal(int, int, bool)  # track_id, clip_id, shift
    tool_action_requested = Signal(int, str, int)  # track_id, tool, project_ms
    empty_area_clicked = Signal(int)       # track_id ??clears selection
    fades_changed = Signal(int)  # track_id ??fade segments added / resized
    speed_changed = Signal(int)  # track_id ??speed segments added / changed
    media_dropped = Signal(int, object)  # track_id, Path ??any media file
    ar_pbr_asset_dropped = Signal(object, int)  # Path, project_ms
    performance_source_dropped = Signal(object, int)  # Path, project_ms
    typography_double_clicked = Signal(int, int)    # track_id, clip_id
    typography_context_menu = Signal(int, int, object)   # track_id, clip_id, global pos
    typography_changed = Signal(int)                # track_id ??add/move/resize
    typography_actor_selected = Signal(int, int)    # track_id, actor_id (0=deselect)
    zoom_double_clicked = Signal(int, int)          # track_id, zoom_actor_id
    zoom_context_menu = Signal(int, int, object)    # track_id, zoom_actor_id, global pos
    zoom_changed = Signal(int)                      # track_id ??add/move/resize
    clip_context_menu = Signal(int, int, object)    # track_id, clip_id, global pos
    clip_badge_action_requested = Signal(int, int, str)  # track_id, clip_id, badge action
    clip_badge_context_menu = Signal(int, int, str, object)  # track_id, clip_id, badge action, global pos
    editor_preset_dropped = Signal(int, object, int)  # track_id, preset dict, project_ms

    def __init__(self, track: VideoTrack) -> None:
        super().__init__()
        self.track = track
        self._is_active: bool = False
        self._lane_index: int = 1
        self._position_ms: int = 0  # project time
        self._march_offset: int = 0   # marching-ants selection animation offset
        self._dragging_playhead: bool = False
        self._dragging_offset: bool = False
        self._resizing_fade: FadeSegment | None = None
        self._resize_side: str = ""  # "left" or "right"
        self._resize_orig_start: int = 0
        self._resize_orig_end: int = 0
        self._drag_start_ms: int = 0
        self._drag_start_x: int = 0
        self._drag_start_offset_ms: int = 0
        # Phase 1.5d Step B: which clip the user grabbed and where it
        # started ??populated by ``mousePressEvent`` and consumed in
        # ``mouseMoveEvent``. ``_drag_clip_id`` is None when the press
        # didn't land on a clip body.
        self._drag_clip_id: int | None = None
        self._drag_start_clip_in_ms: int = 0
        self._drag_group_clip_starts: dict[int, int] = {}
        self._drag_last_cross_track_delta_ms: int = 0
        self._drag_snap_x: int | None = None
        self._drag_feedback_text: str = ""
        self._drag_feedback_x: int | None = None
        self._drag_feedback_tone: str = ""
        self._drag_block_reason: str = ""
        self._drag_block_detail: str = ""
        self._drag_feedback_started_at: float = 0.0
        self._drag_preview_start_ms: int | None = None
        self._drag_preview_end_ms: int | None = None
        self._drag_preview_tone: str = ""
        self._drag_preview_started_at: float = 0.0
        self._hover_hint_text: str = ""
        self._hover_hint_x: int | None = None
        self._hover_hint_started_at: float = 0.0
        self._clip_drag_validator = None
        # Option C: per-row "currently selected" clip IDs, set by
        # the editor via ``set_selected_clip_ids`` so paintEvent can
        # paint the Tiger Orange selection border.
        self._selected_clip_ids: set[int] = set()
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        # Typography-actor drag state
        self._typo_drag_mode: str | None = None
        self._typo_drag_actor_id: int | None = None
        self._typo_drag_anchor_ms: int = 0
        self._typo_drag_orig_start_ms: int = 0
        self._typo_drag_orig_end_ms: int = 0
        # Zoom-actor drag state
        self._zoom_drag_mode: str | None = None
        self._zoom_drag_actor_id: int | None = None
        self._zoom_drag_anchor_ms: int = 0
        self._zoom_drag_orig_start_ms: int = 0
        self._zoom_drag_orig_end_ms: int = 0
        self._zoom_drag_orig_in_ms: int = 0
        self._zoom_drag_orig_out_ms: int = 0
        # Hover tracking for edge-handle highlighting
        self._hover_fade: FadeSegment | None = None
        self._hover_fade_side: str = ""
        self._hover_typo_actor_id: int | None = None
        self._hover_typo_side: str = ""
        self._hover_speed_seg: SpeedSegment | None = None
        self._hover_speed_side: str = ""
        # Speed-segment drag state
        self._speed_drag_mode: str | None = None
        self._speed_drag_seg: SpeedSegment | None = None
        self._speed_drag_anchor_ms: int = 0
        self._speed_drag_orig_start: int = 0
        self._speed_drag_orig_end: int = 0
        # Extra snap targets (ms) passed from the editor ??playhead +
        # timeline markers. Updated by VideoEditorWindow whenever the
        # marker list or playhead changes.
        self._extra_snap_targets: list[int] = []
        self._edit_tool_mode: str = "select"
        self._slip_drag_clip = None
        self._slip_drag_anchor_ms: int = 0
        self._slip_drag_orig_src_in: int = 0
        self._slip_drag_orig_src_out: int = 0
        self._slide_drag_clip = None
        self._slide_prev_clip = None
        self._slide_next_clip = None
        self._slide_drag_anchor_ms: int = 0
        self._slide_orig_target_tl_in: int = 0
        self._slide_orig_prev_src_out: int = 0
        self._slide_orig_next_src_in: int = 0
        self._slide_orig_next_tl_in: int = 0
        # Clip edge trim / roll-edit drag state.
        # ``_clip_trim_clip`` is the clip being trimmed (left or right edge).
        # ``_clip_trim_side`` is "left" or "right".
        # ``_clip_trim_orig_src_in/out`` are the original source timestamps.
        # ``_clip_trim_orig_tl_in`` is the original timeline_in_ms.
        # ``_clip_trim_anchor_ms`` is the project-time ms where the drag began.
        # ``_clip_trim_mode`` is "trim_r", "trim_l", "ripple_r", "ripple_l",
        # or "roll" to distinguish the different edit types.
        # ``_clip_trim_roll_right`` is clip B for roll edits.
        self._clip_trim_clip = None       # VideoClip | None
        self._clip_trim_side: str = ""    # "left" or "right"
        self._clip_trim_mode: str = ""    # "trim_r" / "trim_l" / "ripple_r" / "ripple_l" / "roll"
        self._clip_trim_orig_src_in: int = 0
        self._clip_trim_orig_src_out: int = 0
        self._clip_trim_orig_tl_in: int = 0
        self._clip_trim_anchor_ms: int = 0
        self._clip_trim_roll_right = None  # VideoClip | None (roll edit only)
        self._clip_trim_roll_orig_src_in: int = 0
        self._clip_trim_roll_orig_tl_in: int = 0
        # Transition drag-drop state ??clip ID that is the current drop
        # target (its right edge highlighted with an orange line while a
        # TransitionCard is dragged over the row).
        self._drop_target_clip_id: int | None = None
        self._drop_guide_x: int | None = None
        self._drop_guide_label: str = ""
        self._drop_guide_detail: str = ""
        self._drop_guide_width_px: int = 0
        self._drop_guide_segments: list[dict] = []
        self._effect_drop_target_clip_id: int | None = None
        self._effect_drop_target_label: str = ""
        self._effect_drop_blocked_label: str = ""
        self._effect_drop_blocked_x: int | None = None
        # CapCut-style transition block interaction state.
        self._hovered_transition_clip_id: int | None = None
        self._dragging_transition: bool = False
        self._drag_transition_clip = None   # VideoClip | None
        self._drag_transition_side: str = ""   # "left" or "right"
        self._drag_transition_start_ms: int = 0  # original ms before drag
        self._drag_transition_start_x: int = 0   # mouse x at drag start
        self._timeline_bursts: list[dict] = []

        self.setFixedHeight(self.LABEL_H + self.TIMELINE_H + TRACK_V_PADDING)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.setAcceptDrops(True)
        self._recalc_width()

    def set_selected_clip_ids(self, ids: set[int]) -> None:
        self._selected_clip_ids = set(int(i) for i in ids)
        self.update()

    def set_lane_index(self, index: int) -> None:
        lane = max(1, int(index))
        if lane == self._lane_index:
            return
        self._lane_index = lane
        self.update()

    def set_clip_drag_validator(self, validator) -> None:
        """Install an editor-owned preflight callback for clip drag deltas."""
        self._clip_drag_validator = validator

    @staticmethod
    def _format_drag_time(ms: int | float | None) -> str:
        try:
            value = max(0, int(ms or 0))
        except Exception:
            value = 0
        total = value // 1000
        minutes = total // 60
        seconds = total % 60
        tenth = (value % 1000) // 100
        if minutes:
            return f"{minutes}:{seconds:02d}.{tenth}"
        return f"{seconds}.{tenth}s"

    def _set_drag_feedback(self, text: str, project_ms: int | None = None, tone: str = "move") -> None:
        text = str(text or "")
        tone = str(tone or "move")
        if text != self._drag_feedback_text or tone != self._drag_feedback_tone:
            self._drag_feedback_started_at = time.monotonic()
            self._queue_feedback_animation()
        self._drag_feedback_text = text
        self._drag_feedback_tone = tone
        if project_ms is None:
            self._drag_feedback_x = None
        else:
            try:
                self._drag_feedback_x = self._project_ms_to_x(int(project_ms))
            except Exception:
                self._drag_feedback_x = None
        self.update()

    def _queue_feedback_animation(self) -> None:
        for delay in (24, 48, 80, 120, 170):
            QTimer.singleShot(delay, self.update)

    def _blocked_drag_feedback_text(self) -> str:
        reason = str(getattr(self, "_drag_block_reason", "") or "")
        if reason:
            reason_text = tr(f"veditor.timeline.drag.block_reason.{reason}")
            return tr("veditor.timeline.drag.blocked_with_reason", reason=reason_text)
        detail = str(getattr(self, "_drag_block_detail", "") or "")
        if detail:
            return tr("veditor.timeline.drag.blocked_with_reason", reason=detail)
        return tr("veditor.timeline.drag.blocked")

    def _set_drag_preview(self, start_ms: int | None, end_ms: int | None, tone: str = "move") -> None:
        if start_ms is None or end_ms is None:
            self._drag_preview_start_ms = None
            self._drag_preview_end_ms = None
            self._drag_preview_tone = ""
        else:
            start = max(0, int(start_ms))
            end = max(start + 1, int(end_ms))
            tone = str(tone or "move")
            if (
                start != self._drag_preview_start_ms
                or end != self._drag_preview_end_ms
                or tone != self._drag_preview_tone
            ):
                self._drag_preview_started_at = time.monotonic()
                self._queue_feedback_animation()
            self._drag_preview_start_ms = max(0, int(start_ms))
            self._drag_preview_end_ms = max(self._drag_preview_start_ms + 1, int(end_ms))
            self._drag_preview_tone = tone
        self.update()

    def _set_hover_hint(self, text: str, project_ms: int | None = None) -> None:
        text = str(text or "")
        try:
            x = self._project_ms_to_x(int(project_ms)) if project_ms is not None else None
        except Exception:
            x = None
        if text != self._hover_hint_text or x != self._hover_hint_x:
            if text:
                self._hover_hint_started_at = time.monotonic()
                self._queue_feedback_animation()
            self._hover_hint_text = text
            self._hover_hint_x = x
            self.update()
        # Keep the native tooltip synced even when the hover hint text did not
        # change. Clip effect tooltips are refreshed earlier in mouseMoveEvent
        # and can otherwise clear a still-active affordance hint.
        if self.toolTip() != text:
            self.setToolTip(text)

    def _drag_source_label(self, source: str) -> str:
        source = str(source or "")
        if source == "project start":
            return tr("veditor.timeline.drag.source.project_start")
        if source == "marker/playhead":
            return tr("veditor.timeline.drag.source.marker_playhead")
        if source == "clip edge":
            return tr("veditor.timeline.drag.source.clip_edge")
        return source or tr("veditor.timeline.drag.source.target")

    def _set_drag_constraint_feedback(self, result, clip) -> None:
        if result is None:
            self._clear_drag_feedback()
            return
        if getattr(result, "collided", False):
            text = tr(
                "veditor.timeline.drag.collision_avoided",
                time=self._format_drag_time(getattr(result, "timeline_in_ms", 0)),
            )
            tone = "blocked"
        elif getattr(result, "snapped", False):
            edge = str(getattr(result, "snap_edge", "") or "edge").upper()
            source = self._drag_source_label(str(getattr(result, "snap_source", "") or "target"))
            text = tr(
                "veditor.timeline.drag.snap",
                edge=edge,
                source=source,
                time=self._format_drag_time(getattr(result, "snap_target_ms", 0)),
            )
            tone = "snap"
        elif int(getattr(result, "timeline_in_ms", 0)) != int(getattr(result, "requested_timeline_in_ms", 0)):
            text = tr(
                "veditor.timeline.drag.clamp",
                time=self._format_drag_time(getattr(result, "timeline_in_ms", 0)),
            )
            tone = "blocked"
        else:
            text = tr(
                "veditor.timeline.drag.move",
                time=self._format_drag_time(getattr(result, "timeline_in_ms", 0)),
            )
            tone = "move"
        project_ms = int(getattr(result, "snap_target_ms", None) or getattr(result, "timeline_in_ms", 0) or 0)
        self._set_drag_feedback(text, project_ms, tone)
        length = int(getattr(clip, "effective_length_ms", 0) or 0)
        start = int(getattr(result, "timeline_in_ms", 0) or 0)
        self._set_drag_preview(start, start + max(1, length), tone)

    def _clear_drag_feedback(self) -> None:
        if (
            self._drag_feedback_text
            or self._drag_feedback_x is not None
            or self._drag_feedback_tone
            or self._drag_block_reason
            or self._drag_block_detail
            or self._drag_preview_start_ms is not None
            or self._drag_preview_end_ms is not None
        ):
            self._drag_feedback_text = ""
            self._drag_feedback_x = None
            self._drag_feedback_tone = ""
            self._drag_block_reason = ""
            self._drag_block_detail = ""
            self._drag_feedback_started_at = 0.0
            self._drag_preview_start_ms = None
            self._drag_preview_end_ms = None
            self._drag_preview_tone = ""
            self._drag_preview_started_at = 0.0
            self.update()

    def flash_timeline_burst(self, kind: str, project_ms: int) -> None:
        """Queue a short painter-native burst at a timeline position."""
        from PySide6.QtCore import QTimer

        self._timeline_bursts.append({
            "kind": str(kind or "edit"),
            "project_ms": int(project_ms),
            "started": time.monotonic(),
            "duration": 0.28,
        })
        self.update()
        for delay in (40, 80, 120, 180, 240, 300):
            QTimer.singleShot(delay, self.update)

    def _can_apply_clip_drag_delta(self, clip_ids, delta_ms: int) -> bool:
        delta = int(delta_ms)
        if delta == 0:
            self._drag_block_reason = ""
            self._drag_block_detail = ""
            return True
        validator = getattr(self, "_clip_drag_validator", None)
        if not callable(validator):
            self._drag_block_reason = ""
            self._drag_block_detail = ""
            return True
        try:
            result = validator(
                int(self.track.id),
                {int(clip_id) for clip_id in (clip_ids or [])},
                delta,
            )
        except Exception:
            self._drag_block_reason = ""
            self._drag_block_detail = ""
            return True
        self._drag_block_reason = ""
        self._drag_block_detail = ""
        if isinstance(result, dict):
            ok = bool(result.get("ok", False))
            if ok:
                return True
            self._drag_block_reason = str(result.get("reason", "") or "")
            self._drag_block_detail = str(result.get("message", "") or "")
            _append_ux_event(
                "timeline.drag.blocked",
                track_id=int(self.track.id),
                clip_ids=sorted(int(clip_id) for clip_id in (clip_ids or [])),
                delta_ms=delta,
                reason=self._drag_block_reason,
                detail=self._drag_block_detail,
            )
            return False
        if isinstance(result, str):
            if result:
                self._drag_block_detail = result
                _append_ux_event(
                    "timeline.drag.blocked",
                    track_id=int(self.track.id),
                    clip_ids=sorted(int(clip_id) for clip_id in (clip_ids or [])),
                    delta_ms=delta,
                    reason="",
                    detail=self._drag_block_detail,
                )
                return False
            return True
        allowed = bool(result)
        if not allowed:
            _append_ux_event(
                "timeline.drag.blocked",
                track_id=int(self.track.id),
                clip_ids=sorted(int(clip_id) for clip_id in (clip_ids or [])),
                delta_ms=delta,
                reason="",
                detail="",
            )
        return allowed

    def set_extra_snap_targets(self, targets: list[int]) -> None:
        """Extra project-ms snap targets (playhead + markers) injected by
        the editor so clip drags also snap to these positions."""
        self._extra_snap_targets = list(targets)

    def set_edit_tool_mode(self, mode: str) -> None:
        self._edit_tool_mode = str(mode or "select")
        self.refresh_edit_tool_cursor()
        self.update()

    def refresh_edit_tool_cursor(self, phase: int = 0) -> None:
        self.setCursor(_timeline_tool_cursor(getattr(self, "_edit_tool_mode", "select"), phase))

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self._recalc_width()

    def _preferred_width(self) -> int:
        """Content-driven width before any stretching. Spans up to the
        rightmost edge of either the legacy ``offset+duration`` or any
        clip on the track ??multi-clip drags can push a clip past the
        legacy span, so the row needs to keep up."""
        if self.track.duration_ms <= 0 and not getattr(self.track, "clips", None):
            return MIN_TRACK_WIDTH
        legacy_end = self.track.offset_ms + self.track.duration_ms
        clip_end = 0
        for c in getattr(self.track, "clips", ()):
            if c.timeline_out_ms > clip_end:
                clip_end = c.timeline_out_ms
        span_ms = max(legacy_end, clip_end)
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

    def _track_span_ms(self) -> int:
        """Total occupied span on the project timeline in ms.

        For single-source tracks this equals ``track.offset_ms +
        track.duration_ms``.  For multi-source tracks (``source_path``
        is None, clips carried in ``track.clips``) the legacy
        ``duration_ms`` stays 0, so we derive the span from the clip
        list instead.  Returns 0 when there is no content."""
        legacy_end = self.track.offset_ms + self.track.duration_ms
        clip_end = max(
            (int(c.timeline_out_ms) for c in getattr(self.track, "clips", ())),
            default=0,
        )
        return max(legacy_end, clip_end)

    def _timeline_rect(self) -> QRect:
        """Rect of the WHOLE track strip (clip + gaps) in widget coords.
        Used for hit-testing the strip and clipping thumbnails ??the
        actual clip body fill happens per-clip inside ``paintEvent``.

        Always derived from the clip list when clips are present so that
        appended clips (via ``_append_clip_to_track``) are included even
        when ``track.duration_ms`` still reflects only the original source.
        Falls back to the legacy ``offset_ms + duration_ms`` span when
        there are no clips yet."""
        clips = list(getattr(self.track, "clips", ()))
        if clips:
            # Bounding box across ALL clips (single-source or multi-source).
            left_ms = min(int(c.timeline_in_ms) for c in clips)
            right_ms = max(int(c.timeline_out_ms) for c in clips)
            x = int(self.MARGIN + left_ms / 1000.0 * self._px_per_sec)
            w = max(0, int((right_ms - left_ms) / 1000.0 * self._px_per_sec))
        else:
            offset_px = int(self.track.offset_ms / 1000.0 * self._px_per_sec)
            duration_px = int(self.track.duration_ms / 1000.0 * self._px_per_sec)
            x = self.MARGIN + offset_px
            w = max(0, duration_px)
        return QRect(x, self.LABEL_H, w, self.TIMELINE_H)

    def _clip_rect(self, clip) -> QRect:
        """Phase 1.5c: rect of a single clip's body in widget coords.
        Returns an empty rect if the clip has zero / negative width."""
        x1 = self._project_ms_to_x(int(clip.timeline_in_ms))
        x2 = self._project_ms_to_x(int(clip.timeline_out_ms))
        return QRect(x1, self.LABEL_H, max(0, x2 - x1), self.TIMELINE_H)

    def _hit_test_clip(self, pos: QPoint):
        """Phase 1.5d Step B: return the ``VideoClip`` whose body rect
        contains the cursor, or ``None``. Iterates in clip-list order
        ??for overlapping clips the first match wins, but the cut /
        split paths keep clips disjoint so this isn't an issue today."""
        for clip in getattr(self.track, "clips", ()):
            if self._clip_rect(clip).contains(pos):
                return clip
        return None

    def _clip_at(self, pos: QPoint):
        """Compatibility wrapper used by older context-menu code paths."""
        return self._hit_test_clip(pos)

    def _find_clip_by_id(self, clip_id: int):
        for clip in getattr(self.track, "clips", ()):
            if int(clip.id) == int(clip_id):
                return clip
        return None

    def _adjacent_clip_bounds(self, clip) -> tuple[int, int | None]:
        """Return previous out-ms and next in-ms around ``clip``."""
        clips = sorted(
            getattr(self.track, "clips", []),
            key=lambda c: int(c.timeline_in_ms),
        )
        prev_out = 0
        next_in: int | None = None
        for idx, cur in enumerate(clips):
            if cur is not clip:
                continue
            if idx > 0:
                prev_out = int(clips[idx - 1].timeline_out_ms)
            if idx + 1 < len(clips):
                next_in = int(clips[idx + 1].timeline_in_ms)
            break
        return prev_out, next_in

    def _slide_neighbours(self, clip):
        clips = sorted(
            getattr(self.track, "clips", []),
            key=lambda c: int(c.timeline_in_ms),
        )
        for idx, cur in enumerate(clips):
            if cur is not clip:
                continue
            if idx <= 0 or idx + 1 >= len(clips):
                return None, None
            prev_clip = clips[idx - 1]
            next_clip = clips[idx + 1]
            if abs(int(prev_clip.timeline_out_ms) - int(clip.timeline_in_ms)) > 1:
                return None, None
            if abs(int(next_clip.timeline_in_ms) - int(clip.timeline_out_ms)) > 1:
                return None, None
            return prev_clip, next_clip
        return None, None

    def _apply_slide_delta(self, raw_delta_ms: int) -> bool:
        clip = self._slide_drag_clip
        prev_clip = self._slide_prev_clip
        next_clip = self._slide_next_clip
        if clip is None or prev_clip is None or next_clip is None:
            return False

        prev_src_in = int(prev_clip.source_in_ms)
        prev_src_out = int(self._slide_orig_prev_src_out)
        next_src_in = int(self._slide_orig_next_src_in)
        next_src_out = int(next_clip.effective_source_out_ms)
        prev_len = prev_src_out - prev_src_in
        next_len = next_src_out - next_src_in

        min_delta = -int(self._slide_orig_target_tl_in)
        min_delta = max(min_delta, -(prev_len - self.CLIP_MIN_DURATION_MS))
        min_delta = max(min_delta, -next_src_in)

        max_delta = next_len - self.CLIP_MIN_DURATION_MS
        prev_source_duration = int(getattr(prev_clip, "source_duration_ms", 0) or 0)
        if prev_source_duration > 0:
            max_delta = min(max_delta, prev_source_duration - prev_src_out)

        delta = max(int(min_delta), min(int(max_delta), int(raw_delta_ms)))
        new_prev_src_out = prev_src_out + delta
        new_next_src_in = next_src_in + delta
        if new_prev_src_out <= prev_src_in + self.CLIP_MIN_DURATION_MS:
            return False
        if next_src_out <= new_next_src_in + self.CLIP_MIN_DURATION_MS:
            return False

        clip.timeline_in_ms = int(self._slide_orig_target_tl_in + delta)
        prev_clip.source_out_ms = int(new_prev_src_out)
        next_clip.source_in_ms = int(new_next_src_in)
        next_clip.timeline_in_ms = int(self._slide_orig_next_tl_in + delta)
        self.track.clips.sort(key=lambda c: int(c.timeline_in_ms))
        return True

    def _group_drag_delta(self, raw_delta_ms: int, snap_ms: int) -> int | None:
        """Return a valid delta for the current selected drag group."""
        if not self._drag_group_clip_starts:
            return raw_delta_ms
        group_ids = set(self._drag_group_clip_starts)
        clips = list(getattr(self.track, "clips", []) or [])
        group = [c for c in clips if int(c.id) in group_ids]
        if not group:
            return None
        raw_delta = int(raw_delta_ms)
        min_start = min(int(v) for v in self._drag_group_clip_starts.values())
        if min_start + raw_delta < 0:
            raw_delta = -min_start

        # Snap the group in/out edges to project start, other clip edges,
        # playhead, and markers.
        starts = self._drag_group_clip_starts
        group_in = min(starts[int(c.id)] for c in group)
        group_out = max(starts[int(c.id)] + int(c.effective_length_ms) for c in group)
        targets = {0, *[int(t) for t in self._extra_snap_targets]}
        for other in clips:
            if int(other.id) in group_ids:
                continue
            targets.add(int(other.timeline_in_ms))
            targets.add(int(other.timeline_out_ms))
        best_delta = raw_delta
        best_dist = snap_ms + 1
        for target in targets:
            for edge in (group_in, group_out):
                cand_delta = int(target) - int(edge)
                dist = abs(cand_delta - raw_delta)
                if dist < best_dist:
                    best_dist = dist
                    best_delta = cand_delta
        if best_dist <= snap_ms:
            raw_delta = best_delta

        # Reject overlaps against clips outside the group.
        moved_windows = []
        for c in group:
            start = starts[int(c.id)] + raw_delta
            end = start + int(c.effective_length_ms)
            if start < 0:
                self._drag_block_reason = "timeline_start"
                self._drag_block_detail = ""
                self._set_drag_feedback(
                    self._blocked_drag_feedback_text(),
                    group_in + raw_delta,
                    "blocked",
                )
                self._set_drag_preview(group_in + raw_delta, group_out + raw_delta, "blocked")
                return None
            moved_windows.append((start, end, c))
        for start, end, _clip in moved_windows:
            for other in clips:
                if int(other.id) in group_ids:
                    continue
                if not (int(other.timeline_out_ms) <= start or end <= int(other.timeline_in_ms)):
                    self._drag_block_reason = "video_collision"
                    self._drag_block_detail = ""
                    self._set_drag_feedback(
                        self._blocked_drag_feedback_text(),
                        group_in + raw_delta,
                        "blocked",
                    )
                    self._set_drag_preview(group_in + raw_delta, group_out + raw_delta, "blocked")
                    return None

        if raw_delta != int(raw_delta_ms):
            self._drag_block_reason = ""
            self._drag_block_detail = ""
            self._drag_snap_x = self._project_ms_to_x(group_in + raw_delta)
            self._set_drag_feedback(
                tr(
                    "veditor.timeline.drag.group_snap",
                    time=self._format_drag_time(group_in + raw_delta),
                ),
                group_in + raw_delta,
                "snap",
            )
            self._set_drag_preview(group_in + raw_delta, group_out + raw_delta, "snap")
        else:
            self._drag_block_reason = ""
            self._drag_block_detail = ""
            self._drag_snap_x = None
            self._set_drag_feedback(
                tr(
                    "veditor.timeline.drag.group_move",
                    time=self._format_drag_time(group_in + raw_delta),
                ),
                group_in + raw_delta,
                "move",
            )
            self._set_drag_preview(group_in + raw_delta, group_out + raw_delta, "move")
        return raw_delta

    def _clip_edge_at(self, pos: "QPoint") -> "tuple | None":
        """Return ``(clip, side, roll_neighbour)`` if the cursor is within
        ``CLIP_EDGE_GRAB_PX`` of a clip's left or right edge inside the
        timeline strip, otherwise ``None``.

        ``roll_neighbour`` is the adjacent clip when the cursor sits exactly
        on the shared boundary of two clips; ``None`` for ordinary trim.
        ``side`` is ``"left"`` or ``"right"`` (relative to the target clip).
        """
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        clips = sorted(
            getattr(self.track, "clips", []),
            key=lambda c: int(c.timeline_in_ms),
        )
        for i, clip in enumerate(clips):
            x1 = self._project_ms_to_x(int(clip.timeline_in_ms))
            x2 = self._project_ms_to_x(int(clip.timeline_out_ms))
            x = pos.x()
            # Right edge hit
            if abs(x - x2) <= self.CLIP_EDGE_GRAB_PX:
                # Check if right neighbour shares this boundary (roll edit)
                roll_right = None
                if i + 1 < len(clips):
                    nxt = clips[i + 1]
                    if abs(int(nxt.timeline_in_ms) - int(clip.timeline_out_ms)) <= 1:
                        roll_right = nxt
                return (clip, "right", roll_right)
            # Left edge hit
            if abs(x - x1) <= self.CLIP_EDGE_GRAB_PX:
                # Check if left neighbour shares this boundary (roll edit)
                roll_left = None
                if i - 1 >= 0:
                    prv = clips[i - 1]
                    if abs(int(clip.timeline_in_ms) - int(prv.timeline_out_ms)) <= 1:
                        roll_left = prv
                return (clip, "left", roll_left)
        return None

    def _project_ms_to_x(self, project_ms: int) -> int:
        """Project-timeline ms ??widget x."""
        return int(self.MARGIN + project_ms / 1000.0 * self._px_per_sec)

    def _x_to_project_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def _ms_to_x(self, ms: int) -> int:
        """Track-local ms ??widget x (accounts for offset)."""
        return self._project_ms_to_x(self.track.offset_ms + ms)

    def _x_to_ms(self, x: int) -> int:
        """Widget x ??track-local ms (clamped to duration).

        For multi-source tracks (source_path=None, duration_ms=0) the
        effective duration is derived from the clip list so that zoom /
        typography actor drags work correctly even before
        ``ProjectPlayer.refresh_tracks`` has had a chance to back-fill
        ``track.duration_ms``."""
        eff_dur = self.track.duration_ms
        if eff_dur <= 0:
            # Fall back to the clip-list span so multi-source tracks
            # don't return 0 for every x-position.
            eff_dur = max(
                (int(c.timeline_out_ms) for c in getattr(self.track, "clips", ())),
                default=0,
            )
        if eff_dur <= 0:
            return 0
        local = self._x_to_project_ms(x) - self.track.offset_ms
        return max(0, min(eff_dur, local))

    def _tracked_bitmap_masks(self) -> list:
        """Return enabled tracked BitmapMask instances for this row."""
        try:
            from app.node_mask import BitmapMask
        except Exception:
            return []
        masks_out: list = []
        for _node, masks in list(getattr(self.track, "node_item_chain", None) or []):
            for mask in masks or []:
                if (
                    isinstance(mask, BitmapMask)
                    and bool(getattr(mask, "track_object", False))
                    and bool(getattr(mask, "enabled", True))
                ):
                    masks_out.append(mask)
        return masks_out

    def _paint_tracking_status_overlay(self, painter: QPainter, rect: QRect) -> None:
        masks = self._tracked_bitmap_masks()
        if not masks:
            return
        cached = 0
        corrections = 0
        failed_frames: set[int] = set()
        for mask in masks:
            try:
                cached += len(getattr(mask, "tracking_cache_bboxes", {}) or {})
                corrections += len(getattr(mask, "correction_bboxes", {}) or {})
                failed_frames.update(
                    int(v) for v in (getattr(mask, "tracking_failed_frames", set()) or set())
                )
            except Exception:
                continue

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        has_fail = bool(failed_frames)
        fill = QColor(150, 45, 45, 215) if has_fail else QColor(38, 95, 78, 210)
        border = QColor(255, 125, 105, 235) if has_fail else QColor(110, 220, 175, 230)
        label = f"Track {cached}"
        if failed_frames:
            label += f"  fail {len(failed_frames)}"
        if corrections:
            label += f"  fix {corrections}"
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        badge_w = min(max(70, fm.horizontalAdvance(label) + 14), max(70, rect.width() - 8))
        badge = QRect(rect.left() + 5, rect.top() + 4, badge_w, 16)
        painter.setBrush(fill)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(badge, 4, 4)
        painter.setPen(QColor("#f6fff9"))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)

        if failed_frames:
            fail_pen = QPen(QColor(255, 80, 70, 235))
            fail_pen.setWidth(2)
            painter.setPen(fail_pen)
            fps = 30.0
            clips = list(getattr(self.track, "clips", []) or [])
            for frame_idx in sorted(failed_frames)[:200]:
                src_ms = int(frame_idx / fps * 1000.0)
                for clip in clips:
                    src_in = int(getattr(clip, "source_in_ms", 0))
                    src_out = int(getattr(clip, "effective_source_out_ms", 0))
                    if src_in <= src_ms < src_out:
                        proj_ms = int(getattr(clip, "timeline_in_ms", 0)) + (src_ms - src_in)
                        x = self._project_ms_to_x(proj_ms)
                        cr = self._clip_rect(clip)
                        if cr.left() <= x <= cr.right():
                            painter.drawLine(x, cr.top() + 2, x, cr.bottom() - 2)
                            break
        painter.restore()

    @staticmethod
    def _effect_param_active(value) -> bool:
        if value is None:
            return False
        is_identity = getattr(value, "is_identity", None)
        if callable(is_identity):
            try:
                return not bool(is_identity())
            except Exception:
                return True
        if isinstance(value, dict):
            if bool(value.get("enabled", False)):
                return True
            for key, item in value.items():
                if str(key) in {
                    "enabled",
                    "name",
                    "label",
                    "preset_id",
                    "preset_meta",
                    "__preset_meta",
                    "kind",
                }:
                    continue
                if item not in (None, False, 0, 0.0, ""):
                    return True
            return False
        return True

    @staticmethod
    def _color_grade_active(value) -> bool:
        if value is None:
            return False
        is_identity = getattr(value, "is_identity", None)
        if callable(is_identity):
            try:
                return not bool(is_identity())
            except Exception:
                return True
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key) in {"preset_id", "name", "label"}:
                    continue
                if item not in (None, False, 0, 0.0, "", [], {}):
                    return True
            return False
        return True

    @staticmethod
    def _clip_color_grade_active(clip) -> bool:
        direct = getattr(clip, "color_grade", None)
        if TrackRow._color_grade_active(direct):
            return True
        graph = getattr(clip, "node_graph", None)
        color = getattr(graph, "color", None)
        grade = getattr(color, "grade", None)
        return TrackRow._color_grade_active(grade)

    @staticmethod
    def _ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
        return int(start_a) < int(end_b) and int(start_b) < int(end_a)

    def _clip_status_badges(self, clip) -> list[tuple[str, str, str]]:
        badges: list[tuple[str, str, str]] = []
        if self._effect_param_active(getattr(clip, "video_filters", None)):
            badges.append(("FX", "#77736D", "#565B66"))
        if self._effect_param_active(getattr(clip, "chroma_key", None)):
            badges.append(("Key", "#60706C", "#53616A"))
        if self._effect_param_active(getattr(clip, "bg_removal", None)):
            badges.append(("AI", "#657063", "#53616A"))
        if (
            not badges
            and (
                self._effect_param_active(getattr(clip, "disabled_video_filters", None))
                or self._effect_param_active(getattr(clip, "disabled_chroma_key", None))
                or self._effect_param_active(getattr(clip, "disabled_bg_removal", None))
            )
        ):
            badges.append(("Off", "#535B72", "#303747"))
        if str(getattr(clip, "transition_out_type", "") or ""):
            badges.append(("TR", "#7A6A50", "#625850"))
        if TrackRow._clip_color_grade_active(clip):
            badges.append(("COL", "#716C7B", "#5A5664"))
        if (getattr(clip, "screenstudio_polish", {}) or {}).get("auto_zoom_actor_ids"):
            badges.append(("AP", "#75645C", "#5C596A"))

        clip_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        clip_end = int(getattr(clip, "timeline_out_ms", clip_start) or clip_start)
        for actor in getattr(self.track, "typography_actors", []) or []:
            if self._ranges_overlap(
                clip_start,
                clip_end,
                int(getattr(actor, "start_ms", 0) or 0),
                int(getattr(actor, "end_ms", 0) or 0),
            ):
                badges.append(("T", "#735E6B", "#5A5667"))
                break
        for zactor in getattr(self.track, "zoom_actors", []) or []:
            if self._ranges_overlap(
                clip_start,
                clip_end,
                int(getattr(zactor, "start_ms", 0) or 0),
                int(getattr(zactor, "end_ms", 0) or 0),
            ):
                badges.append(("Mot", "#5F6E78", "#585A6C"))
                break
        if bool(getattr(clip, "is_nested_sequence", False)) or getattr(clip, "compound_group_id", None) is not None:
            badges.append(("Nest", "#566173", "#585A6C"))
        return badges[:6]

    @staticmethod
    def _effect_param_label(value, fallback: str = "FX") -> str:
        """Return a user-facing label for an applied clip effect payload."""
        if value is None:
            return ""
        meta = getattr(value, "preset_meta", None)
        if not isinstance(meta, dict) and isinstance(value, dict):
            raw_meta = value.get("preset_meta") or value.get("__preset_meta")
            meta = raw_meta if isinstance(raw_meta, dict) else {}
        if isinstance(meta, dict):
            label = str(meta.get("name") or meta.get("id") or "").strip()
            if label:
                return label.replace("-", " ").title()
        if isinstance(value, dict):
            label = str(value.get("name") or value.get("label") or value.get("preset_id") or "").strip()
            if label:
                return label.replace("-", " ").title()
        return fallback

    def _clip_effect_strip_entries(self, clip) -> list[tuple[str, str, str, str]]:
        """Timeline-visible effect/title/transition strips for a clip."""
        entries: list[tuple[str, str, str, str]] = []
        vf = getattr(clip, "video_filters", None)
        if self._effect_param_active(vf):
            entries.append(("FX", self._effect_param_label(vf, "Video FX"), "#77736D", "#565B66"))
        key = getattr(clip, "chroma_key", None)
        if self._effect_param_active(key):
            entries.append(("KEY", self._effect_param_label(key, "Chroma Key"), "#60706C", "#53616A"))
        ai = getattr(clip, "bg_removal", None)
        if self._effect_param_active(ai):
            entries.append(("AI", self._effect_param_label(ai, "Background"), "#657063", "#53616A"))
        ttype = str(getattr(clip, "transition_out_type", "") or "")
        if ttype:
            meta = getattr(clip, "transition_preset_meta", {}) or {}
            pretty = str(meta.get("name") or meta.get("id") or "").strip() if isinstance(meta, dict) else ""
            if not pretty:
                pretty = {
                    "dissolve": "Cross Dissolve",
                    "fade_black": "Fade Black",
                    "fade_white": "Fade White",
                    "slide_left": "Slide",
                    "wipe_left": "Wipe",
                    "zoom_in": "Zoom In",
                    "zoom_out": "Zoom Out",
                    "dip_white": "Dip White",
                }.get(ttype, ttype.replace("_", " ").title())
            pretty = pretty.replace("-", " ").title()
            entries.append(("TR", pretty, "#7A6A50", "#625850"))
        if TrackRow._clip_color_grade_active(clip):
            entries.append(("COL", "Color Grade", "#716C7B", "#5A5664"))
        if (getattr(clip, "screenstudio_polish", {}) or {}).get("auto_zoom_actor_ids"):
            entries.append(("AP", "Auto Zoom", "#75645C", "#5C596A"))
        clip_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        clip_end = int(getattr(clip, "timeline_out_ms", clip_start) or clip_start)
        for actor in getattr(self.track, "typography_actors", []) or []:
            if self._ranges_overlap(
                clip_start,
                clip_end,
                int(getattr(actor, "start_ms", 0) or 0),
                int(getattr(actor, "end_ms", 0) or 0),
            ):
                text = str(getattr(actor, "text", "") or getattr(actor, "label", "") or "Title").strip()
                entries.append(("T", text[:32] or "Title", "#735E6B", "#5A5667"))
                break
        for zactor in getattr(self.track, "zoom_actors", []) or []:
            if self._ranges_overlap(
                clip_start,
                clip_end,
                int(getattr(zactor, "start_ms", 0) or 0),
                int(getattr(zactor, "end_ms", 0) or 0),
            ):
                label = str(getattr(zactor, "label", "") or getattr(zactor, "name", "") or "Zoom/Motion").strip()
                entries.append(("Mot", label[:32] or "Zoom/Motion", "#5F6E78", "#585A6C"))
                break
        if bool(getattr(clip, "is_nested_sequence", False)) or getattr(clip, "compound_group_id", None) is not None:
            entries.append(("Nest", "Nested", "#566173", "#585A6C"))
        return entries[:5]

    @staticmethod
    def _clip_effect_strip_display_text(tag: str, label: str, width_px: int) -> str:
        tag = str(tag or "").strip()
        label = str(label or "").strip()
        if int(width_px) < 32:
            return ""
        if int(width_px) < 86 or not label:
            return tag
        return f"{tag} {label}"

    def _clip_effect_tooltip(self, clip) -> str:
        entries = self._clip_effect_strip_entries(clip)
        if not entries:
            return ""
        lines = [tr("veditor.timeline.applied_elements")]
        for tag, label, _color_a, _color_b in entries:
            lines.append(f"{tag}: {label or tag}")
        lines.append(tr("veditor.timeline.applied_elements_hint"))
        return "\n".join(lines)

    @staticmethod
    def _clip_status_badge_action(label: str) -> str:
        text = str(label or "").casefold()
        if text in {"fx", "key", "ai", "off"}:
            return "fx"
        if text == "tr":
            return "transition"
        if text == "col":
            return "color"
        if text == "ap":
            return "motion"
        if text == "t":
            return "title"
        if text == "mot":
            return "motion"
        if text == "nest":
            return "nested"
        return "inspect"

    def _clip_status_badge_rects(self, clip, clip_rect: QRect) -> list[tuple[str, str, QRect]]:
        badges = self._clip_status_badges(clip)
        if not badges or clip_rect.width() < 34 or clip_rect.height() < 24:
            return []
        font = QFont(self.font())
        font.setPixelSize(7)
        font.setBold(True)
        metrics = QFontMetrics(font)
        x = clip_rect.right() - 4
        y = clip_rect.top() + 4
        min_x = clip_rect.left() + 5
        rects: list[tuple[str, str, QRect]] = []
        for label, _color_a, _color_b in reversed(badges[:4]):
            w = max(17, metrics.horizontalAdvance(label) + 8)
            if x - w < min_x:
                break
            badge_rect = QRect(x - w, y, w, 12)
            rects.append((label, self._clip_status_badge_action(label), badge_rect))
            x = badge_rect.left() - 3
        return rects

    def _clip_status_action_at(self, clip, pos: QPoint) -> str:
        rect = self._clip_rect(clip)
        for _label, action, badge_rect in self._clip_status_badge_rects(clip, rect):
            if badge_rect.adjusted(-3, -3, 3, 3).contains(pos):
                return action
        return ""

    def _paint_clip_status_badges(self, painter: QPainter, clip, clip_rect: QRect) -> None:
        badge_rects = self._clip_status_badge_rects(clip, clip_rect)
        if not badge_rects:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = QFont(painter.font())
        font.setPixelSize(7)
        font.setBold(True)
        painter.setFont(font)
        color_by_label = {label: (color_a, color_b) for label, color_a, color_b in self._clip_status_badges(clip)}
        for label, _action, badge_rect in badge_rects:
            color_a, color_b = color_by_label.get(label, ("#FF7043", "#7E6FFF"))
            accent_a = QColor(color_a)
            accent_b = QColor(color_b)
            accent_a.setAlpha(135)
            accent_b.setAlpha(105)
            grad = QLinearGradient(badge_rect.topLeft(), badge_rect.bottomRight())
            grad.setColorAt(0.0, accent_a)
            grad.setColorAt(1.0, accent_b)
            painter.setPen(QPen(QColor(255, 255, 255, 36), 1))
            painter.setBrush(QColor(20, 22, 27, 172))
            painter.drawRoundedRect(badge_rect, 5, 5)
            accent_rect = QRect(
                badge_rect.left() + 2,
                badge_rect.bottom() - 2,
                max(4, badge_rect.width() - 4),
                1,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(accent_rect, 1, 1)
            painter.setPen(QColor(235, 238, 244, 210))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def _paint_clip_effect_strips(self, painter: QPainter, clip, clip_rect: QRect) -> None:
        entries = self._clip_effect_strip_entries(clip)
        if not entries or clip_rect.height() < 24:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if clip_rect.width() < 72:
            count = min(len(entries), max(1, min(4, max(1, (clip_rect.width() - 8) // 8))))
            dot = max(4, min(6, (clip_rect.width() - 8 - max(0, count - 1) * 2) // max(1, count)))
            total_w = count * dot + max(0, count - 1) * 2
            x = clip_rect.left() + max(3, (clip_rect.width() - total_w) // 2)
            y = clip_rect.bottom() - dot - 4
            for _tag, _label, color_a, color_b in entries[:count]:
                r = QRect(x, y, dot, dot)
                grad = QLinearGradient(r.topLeft(), r.bottomRight())
                a = QColor(color_a)
                b = QColor(color_b)
                a.setAlpha(145)
                b.setAlpha(120)
                grad.setColorAt(0.0, a)
                grad.setColorAt(1.0, b)
                painter.setPen(QPen(QColor(255, 255, 255, 38), 1))
                painter.setBrush(QBrush(grad))
                painter.drawRoundedRect(r, dot // 2, dot // 2)
                x += dot + 2
            painter.restore()
            return
        if clip_rect.height() < 34:
            painter.restore()
            return
        font = QFont(painter.font())
        font.setPixelSize(7)
        font.setBold(False)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        lane_h = 11
        gap = 2
        y = clip_rect.bottom() - lane_h - 3
        x = clip_rect.left() + 5
        max_right = clip_rect.right() - 5
        for tag, label, color_a, color_b in entries:
            available = max_right - x + 1
            if available < 24:
                break
            full_text = f"{tag} {label}" if label else tag
            ideal_w = metrics.horizontalAdvance(full_text) + 14
            w = min(max(28, ideal_w), available)
            text = self._clip_effect_strip_display_text(tag, label, w)
            if not text:
                break
            r = QRect(x, y, w, lane_h)
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            a = QColor(color_a)
            b = QColor(color_b)
            a.setAlpha(68)
            b.setAlpha(54)
            grad.setColorAt(0.0, a)
            grad.setColorAt(1.0, b)
            painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(r, 4, 4)
            accent = QColor(color_a)
            accent.setAlpha(125)
            painter.setPen(QPen(accent, 1))
            painter.drawLine(r.left() + 4, r.top() + 1, r.right() - 4, r.top() + 1)
            painter.setPen(QColor(226, 229, 236, 198))
            painter.drawText(
                r.adjusted(5, 0, -5, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                metrics.elidedText(text, Qt.TextElideMode.ElideRight, r.width() - 10),
            )
            x = r.right() + gap
        painter.restore()

    @staticmethod
    def _color_grade_activity_fields(value) -> list[str]:
        """Return non-identity color controls, used for timeline evidence marks."""
        if not TrackRow._color_grade_active(value):
            return []
        data = None
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            try:
                data = to_dict()
            except Exception:
                data = None
        if data is None and isinstance(value, dict):
            data = dict(value)
        if not isinstance(data, dict):
            return ["grade"]
        skip = {
            "enabled",
            "name",
            "label",
            "preset_id",
            "preset_meta",
            "__preset_meta",
            "kind",
        }
        fields: list[str] = []
        for key, item in data.items():
            key_text = str(key)
            if key_text in skip:
                continue
            active = False
            if isinstance(item, bool):
                active = item
            elif isinstance(item, (int, float)):
                active = abs(float(item)) > 0.0001
            elif isinstance(item, str):
                active = bool(item.strip())
            elif isinstance(item, (list, tuple, dict, set)):
                active = bool(item)
            elif item is not None:
                active = True
            if active:
                fields.append(key_text)
        return fields or ["grade"]

    @staticmethod
    def _append_unique_active_grade(grades: list, value) -> None:
        if not TrackRow._color_grade_active(value):
            return
        if any(existing is value for existing in grades):
            return
        grades.append(value)

    @staticmethod
    def _clip_color_grades(clip) -> list:
        grades: list = []
        TrackRow._append_unique_active_grade(grades, getattr(clip, "color_grade", None))
        graph = getattr(clip, "node_graph", None)
        color = getattr(graph, "color", None)
        TrackRow._append_unique_active_grade(grades, getattr(color, "grade", None))
        return grades

    def _track_color_grades(self) -> list:
        grades: list = []
        for node_item, _masks in list(getattr(self.track, "node_item_chain", None) or []):
            TrackRow._append_unique_active_grade(
                grades,
                getattr(node_item, "color_grade", None),
            )
        for grade in list(getattr(self.track, "color_grade_chain", None) or []):
            TrackRow._append_unique_active_grade(grades, grade)
        TrackRow._append_unique_active_grade(grades, getattr(self.track, "color_grade", None))
        return grades

    def _paint_color_grade_thumbnail_underlay(self, painter: QPainter, clip_rect: QRect) -> None:
        if clip_rect.width() < 12 or clip_rect.height() < 18:
            return
        bleed_px = max(18, min(52, clip_rect.width() // 7))
        underlay = QRect(
            clip_rect.left() - bleed_px,
            clip_rect.top() + 4,
            clip_rect.width() + bleed_px * 2,
            max(1, clip_rect.height() - 8),
        )
        if underlay.width() <= 0 or underlay.height() <= 0:
            return

        edge_stop = max(0.06, min(0.22, bleed_px / max(1.0, float(underlay.width()))))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        shade = QLinearGradient(underlay.topLeft(), underlay.topRight())
        shade.setColorAt(0.0, QColor(0, 0, 0, 0))
        shade.setColorAt(edge_stop, QColor(0, 0, 0, 96))
        shade.setColorAt(0.5, QColor(0, 0, 0, 96))
        shade.setColorAt(1.0 - edge_stop, QColor(0, 0, 0, 96))
        shade.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(shade))
        painter.drawRoundedRect(underlay, 5, 5)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        painter.drawRoundedRect(underlay.adjusted(0, 0, -1, -1), 5, 5)
        painter.restore()

    def _paint_color_grade_layer(self, painter: QPainter, clip, clip_rect: QRect) -> None:
        clip_grades = self._clip_color_grades(clip)
        track_grades = self._track_color_grades()
        if not clip_grades and not track_grades:
            return
        if clip_rect.width() < 28 or clip_rect.height() < 32:
            return

        fields: list[str] = []
        for grade in [*clip_grades, *track_grades]:
            fields.extend(self._color_grade_activity_fields(grade))
        key_count = max(2, min(6, len(fields) if fields else 2))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        inset = 7 if clip_rect.width() > 64 else 3
        rail_h = 9
        rail_y = clip_rect.top() + max(20, clip_rect.height() - 23)
        rail = QRect(
            clip_rect.left() + inset,
            rail_y,
            max(1, clip_rect.width() - inset * 2),
            rail_h,
        )
        painter.setClipRect(clip_rect.adjusted(-60, 1, 60, -1))
        self._paint_color_grade_thumbnail_underlay(painter, clip_rect)
        painter.setClipRect(clip_rect.adjusted(1, 1, -1, -1))

        fill = QLinearGradient(rail.topLeft(), rail.bottomRight())
        fill.setColorAt(0.0, QColor(120, 132, 126, 58))
        fill.setColorAt(0.55, QColor(88, 96, 104, 48))
        fill.setColorAt(1.0, QColor(58, 65, 68, 42))
        painter.setPen(QPen(QColor(222, 226, 220, 42), 1))
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(rail, 3, 3)
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawLine(rail.left() + 4, rail.top() + 1, rail.right() - 4, rail.top() + 1)

        if rail.width() > 118:
            font = QFont(painter.font())
            font.setFamily("Segoe UI Variable")
            font.setPixelSize(7)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor(224, 226, 222, 160))
            label = "Grade Layer 1" if track_grades else "Primary Grade"
            painter.drawText(
                rail.adjusted(6, -1, -6, 1),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, max(10, rail.width() // 3)),
            )

        if rail.width() > 46:
            y = rail.center().y()
            left_pad = 54 if rail.width() > 150 else 12
            usable_w = max(12, rail.width() - left_pad - 9)
            for idx in range(key_count):
                ratio = (idx + 1) / float(key_count + 1)
                x = rail.left() + left_pad + int(usable_w * ratio)
                d = 3
                diamond = QPolygon([
                    QPoint(x, y - d),
                    QPoint(x + d, y),
                    QPoint(x, y + d),
                    QPoint(x - d, y),
                ])
                painter.setBrush(QColor(226, 229, 220, 188))
                painter.setPen(QPen(QColor(16, 18, 20, 110), 1))
                painter.drawPolygon(diamond)
        painter.restore()

    def _catalog_track_palette(self) -> tuple[QColor, QColor, QColor]:
        palettes = (
            ("#5A432F", "#75583A", "#D99B5D"),
            ("#38495D", "#4B627A", "#89B4D6"),
            ("#41533F", "#536C52", "#9ACB8C"),
            ("#51405D", "#665179", "#BE98D8"),
            ("#564B35", "#6D6042", "#D5B36A"),
        )
        try:
            idx = max(0, int(getattr(self.track, "id", 0) or 0) - 1) % len(palettes)
        except Exception:
            idx = 0
        return tuple(QColor(c) for c in palettes[idx])

    def _is_performance_source_track(self) -> bool:
        try:
            from app.vtuber.performance_source import is_performance_source_track

            return bool(is_performance_source_track(self.track))
        except Exception:
            return bool(
                getattr(self.track, "vtuber_performance_source", False)
                or getattr(self.track, "performance_source", False)
                or str(getattr(self.track, "track_type", "") or "").casefold() == "vtuber_performance_source"
            )

    @staticmethod
    def _is_performance_source_clip(clip) -> bool:
        try:
            from app.vtuber.performance_source import is_performance_source_clip

            return bool(is_performance_source_clip(clip))
        except Exception:
            return bool(
                getattr(clip, "vtuber_performance_source", False)
                or getattr(clip, "performance_source", False)
                or str(getattr(clip, "track_type", "") or "").casefold() == "vtuber_performance_source"
            )

    def _track_palette_for_role(self) -> tuple[QColor, QColor, QColor]:
        if self._is_performance_source_track():
            return QColor("#303440"), QColor("#3C4251"), QColor("#868CA0")
        return self._catalog_track_palette()

    @staticmethod
    def _duration_chip_text(duration_ms: int) -> str:
        total = max(0, int(round(max(0, int(duration_ms)) / 1000.0)))
        if total <= 0:
            return ""
        if total < 60:
            return f"{total}s"
        minutes = total // 60
        seconds = total % 60
        return f"{minutes}:{seconds:02d}"


    def _paint_performance_source_badge(self, painter: QPainter, clip_rect: QRect) -> None:
        if clip_rect.width() < 86 or clip_rect.height() < 26:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        badge = QRect(clip_rect.left() + 8, clip_rect.top() + 5, min(106, clip_rect.width() - 16), 16)
        fill = QLinearGradient(badge.topLeft(), badge.bottomRight())
        fill.setColorAt(0.0, QColor(72, 76, 90, 196))
        fill.setColorAt(1.0, QColor(42, 45, 54, 196))
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(QColor(210, 214, 230, 82), 1))
        painter.drawRoundedRect(badge, 5, 5)
        font = QFont(painter.font())
        font.setFamily("Segoe UI Variable")
        font.setPixelSize(8)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(235, 238, 248, 196))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "PERF INPUT")
        painter.restore()


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
        ``fade.kind``: ``in`` = black?萸뻩ntent, ``out`` = content?萸뷿ack,
        ``both`` = content?萸뷿ack?萸뻩ntent (two halves). Resize handles on
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
        else:  # both ??two-half pattern
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

        # Outer frame ??subtle, not orange (orange is reserved for selection)
        pen = QPen(QColor(180, 100, 60, 100))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(fx1, rect.top(), max(1, fx2 - fx1), rect.height())

        # Edge trim handles ??always visible (invites resizing), widen +
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
        """Empty-track slot: 80% brightness diagonal stripes + subtle border."""
        painter.save()
        StripedHost._draw_stripes(
            painter, rect,
            StripedHost.BG_80, StripedHost.STRIPE_80,
        )
        border = QPen(QColor("#3e3e4a"))
        border.setWidth(1)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.restore()

    @staticmethod
    def _draw_speed_label(
        painter: QPainter, speed: float, x: int, y: int, w: int, h: int,
        frame_blend: bool = False,
    ) -> None:
        """Draw a bold ?엜peed badge clamped inside the segment rect. Picks a
        font size proportional to the segment box, capped so it never spills
        outside the track frame.  When ``frame_blend`` is True a tilde suffix
        (``~``) is appended to hint that smooth interpolation is active."""
        if w < 14:
            return
        label = f"x{speed:g}" + ("~" if frame_blend else "")
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



    def leaveEvent(self, _event) -> None:
        # Clear hover state when the cursor exits the widget, otherwise
        # the last-hovered handle stays "hot" forever. Qt fires an
        # early leaveEvent during construction (before the hover fields
        # are set) when the host invalidates layout right after
        # insertWidget ??guard with getattr so the widget doesn't crash
        # mid-build.
        if (getattr(self, "_hover_fade", None) is not None
                or getattr(self, "_hover_typo_actor_id", None) is not None
                or getattr(self, "_hover_speed_seg", None) is not None
                or getattr(self, "_hover_hint_text", "")):
            self._hover_fade = None
            self._hover_fade_side = ""
            self._hover_typo_actor_id = None
            self._hover_typo_side = ""
            self._hover_speed_seg = None
            self._hover_speed_side = ""
            self._set_hover_hint("")
            self.update()

    def wheelEvent(self, event) -> None:
        """Scroll wheel over a speed segment cycles through preset
        rates ??gives users a quick way to tweak the speed in place
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


    # ---- Transition helpers ----

    _TRANSITION_EDGE_PX = 20  # px from right edge of clip to trigger transition menu

    def _transition_clip_at(self, pos: QPoint):
        """Return the VideoClip whose right edge is within
        ``_TRANSITION_EDGE_PX`` of ``pos``, or None."""
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        for clip in (getattr(self.track, "clips", None) or []):
            cr = self._clip_rect(clip)
            if cr.width() <= 0:
                continue
            right_x = cr.right()
            if abs(pos.x() - right_x) <= self._TRANSITION_EDGE_PX and cr.top() <= pos.y() <= cr.bottom():
                return clip
        return None

    # ---- CapCut-style transition helpers ----

    _BOUNDARY_HIT_PX = 10   # px either side of a clip boundary to detect click
    _TRANSITION_HANDLE_PX = 8  # px from edge of transition block for handle grab

    def _clip_at_boundary(self, pos: QPoint):
        """Return the LEFT VideoClip if ``pos`` is at the boundary (gap ??5 px)
        between two adjacent clips AND that clip has no transition yet.
        Returns None otherwise."""
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None
        clips = sorted(
            (getattr(self.track, "clips", None) or []),
            key=lambda c: int(c.timeline_in_ms),
        )
        for i in range(len(clips) - 1):
            left_clip = clips[i]
            right_clip = clips[i + 1]
            gap_ms = int(right_clip.timeline_in_ms) - int(left_clip.timeline_out_ms)
            if gap_ms > 5:
                # More than 5 ms gap ??not adjacent, skip
                continue
            boundary_x = self._project_ms_to_x(int(left_clip.timeline_out_ms))
            if abs(pos.x() - boundary_x) <= self._BOUNDARY_HIT_PX:
                # Don't insert if the clip already has a transition block
                if getattr(left_clip, "transition_out_type", ""):
                    return None
                return left_clip
        return None

    def _transition_rect(self, clip, sorted_clips=None):
        """Return the QRect of the transition block for ``clip`` if it has
        ``transition_out_type != ""``, spanning half the block into this clip
        and half into the next adjacent clip. Returns None if no transition or
        no adjacent next clip."""
        ttype = getattr(clip, "transition_out_type", "")
        if not ttype:
            return None
        t_ms = max(100, int(getattr(clip, "transition_out_ms", 500)))
        t_px = max(16, int(t_ms / 1000.0 * self._px_per_sec))
        half = t_px // 2

        boundary_x = self._project_ms_to_x(int(clip.timeline_out_ms))
        y_top = self.LABEL_H
        h_px = self.TIMELINE_H
        return QRect(boundary_x - half, y_top, t_px, h_px)

    def _transition_handle_at(self, pos: QPoint):
        """Return (clip, 'left' | 'right') if ``pos`` is on the left or right
        edge handle of an existing transition block, (None, '') otherwise."""
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.TIMELINE_H:
            return None, ""
        clips = sorted(
            (getattr(self.track, "clips", None) or []),
            key=lambda c: int(c.timeline_in_ms),
        )
        for clip in clips:
            t_rect = self._transition_rect(clip, clips)
            if t_rect is None:
                continue
            if not t_rect.contains(pos):
                continue
            # Determine which handle: left or right based on x position
            mid_x = t_rect.left() + t_rect.width() // 2
            if pos.x() <= mid_x:
                return clip, "left"
            else:
                return clip, "right"
        return None, ""

    def _get_current_transition_type(self) -> tuple:
        """Return (type_str, duration_ms) for the currently selected transition
        in the TransitionsPanel. Falls back to ('dissolve', 500) if not found."""
        # Walk up the widget hierarchy to find the VideoEditorWindow which holds
        # self._transitions_panel. We stop after 20 levels to avoid infinite loops.
        w = self.parent()
        for _ in range(20):
            if w is None:
                break
            panel = getattr(w, "_transitions_panel", None)
            if panel is not None:
                # Find the most-recently-hovered card (cards track _hovered flag)
                ms = int(getattr(panel, "_default_ms", 500))
                # Look for a selected / last-hovered card
                for card in getattr(panel, "_cards", []):
                    if getattr(card, "_hovered", False):
                        return (str(card._ttype), ms)
                # No card hovered ??use the first card's type
                cards = getattr(panel, "_cards", [])
                if cards:
                    return (str(cards[0]._ttype), ms)
                return ("dissolve", ms)
            w = w.parent()
        return ("dissolve", 500)


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
        # Double-click on a typography / zoom actor opens its editor;
        # on a fade segment, deletes it.
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        pos = event.position().toPoint()
        zactor, _z = self._zoom_at(pos)
        if zactor is not None:
            self.zoom_double_clicked.emit(self.track.id, zactor.id)
            return
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

    def _zoom_actor_rect(self, zactor: ZoomActor, strip_rect: QRect) -> QRect:
        """Rect of a zoom actor chip in widget coords. Sits at the
        BOTTOM of the timeline strip so it doesn't fight with typography
        at the top."""
        x1 = self._ms_to_x(int(zactor.start_ms))
        x2 = self._ms_to_x(int(zactor.end_ms))
        w = max(2, x2 - x1)
        top = strip_rect.bottom() - self.ZOOM_CHIP_H - 2
        return QRect(x1, top, w, self.ZOOM_CHIP_H)



    def _zoom_at(self, pos: QPoint) -> "tuple[ZoomActor | None, str]":
        """Hit-test the zoom-actor strip. Returns ``(actor, zone)``:

            "left"      outer left edge ??resize total length
            "fade_in"   inner handle at start + zoom_in_ms ??fade-in time
            "body"      anywhere else inside ??drag to move
            "fade_out"  inner handle at end - zoom_out_ms ??fade-out time
            "right"     outer right edge ??resize total length

        ``(None, "")`` when the point isn't on any zoom actor."""
        rect = self._timeline_rect()
        handle_grab = 6
        for zactor in getattr(self.track, "zoom_actors", []):
            r = self._zoom_actor_rect(zactor, rect)
            if not r.contains(pos):
                continue
            x = pos.x()
            # Outer resize edges ??change start_ms / end_ms.
            if x - r.left() <= self.ZOOM_EDGE_GRAB_PX:
                return zactor, "left"
            if r.right() - x <= self.ZOOM_EDGE_GRAB_PX:
                return zactor, "right"
            # Inner fade-time handles.
            in_x = self._ms_to_x(zactor.start_ms + zactor.zoom_in_ms)
            out_x = self._ms_to_x(zactor.end_ms - zactor.zoom_out_ms)
            if abs(x - in_x) <= handle_grab:
                return zactor, "fade_in"
            if abs(x - out_x) <= handle_grab:
                return zactor, "fade_out"
            return zactor, "body"
        return None, ""

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

    def _drop_guide_text(self, md: QMimeData) -> str:
        return _shared_drop_guide_text(md)

    def _drop_guide_width_for_mime(self, md: QMimeData) -> int:
        return _shared_drop_guide_width_for_mime(
            md,
            px_per_sec=float(getattr(self, "_px_per_sec", 40.0)),
        )

    def _drop_guide_segments_for_mime(self, md: QMimeData) -> list[dict]:
        return _shared_drop_guide_segments_for_mime(md)

    def _drop_guide_detail_for_mime(self, md: QMimeData) -> str:
        return _shared_drop_guide_detail_for_mime(
            md,
            effect_default_label=tr("veditor.effect_preset.default"),
        )

    def _effect_preset_drag_label(self, md: QMimeData) -> str:
        return _shared_effect_preset_drag_label(
            md,
            default=tr("veditor.effect_preset.default"),
        )

    def _update_effect_drop_target(self, pos: QPoint, md: QMimeData) -> None:
        if not md.hasFormat(EFFECT_PRESET_MIME_TYPE):
            self._clear_effect_drop_target()
            return
        clip = self._hit_test_clip(pos)
        target_id = int(getattr(clip, "id", -1)) if clip is not None else None
        label = self._effect_preset_drag_label(md)
        blocked_label = "" if clip is not None else label
        blocked_x = int(pos.x()) if clip is None else None
        if (
            target_id != self._effect_drop_target_clip_id
            or label != self._effect_drop_target_label
            or blocked_label != self._effect_drop_blocked_label
            or blocked_x != self._effect_drop_blocked_x
        ):
            self._effect_drop_target_clip_id = target_id
            self._effect_drop_target_label = label
            self._effect_drop_blocked_label = blocked_label
            self._effect_drop_blocked_x = blocked_x
            self.update()

    def _clear_effect_drop_target(self) -> None:
        if (
            self._effect_drop_target_clip_id is not None
            or self._effect_drop_target_label
            or self._effect_drop_blocked_label
            or self._effect_drop_blocked_x is not None
        ):
            self._effect_drop_target_clip_id = None
            self._effect_drop_target_label = ""
            self._effect_drop_blocked_label = ""
            self._effect_drop_blocked_x = None
            self.update()

    def _update_drop_guide(self, pos: QPoint, md: QMimeData) -> None:
        x = max(self.MARGIN, min(int(pos.x()), self.width() - self.MARGIN))
        label = self._drop_guide_text(md)
        width_px = self._drop_guide_width_for_mime(md)
        segments = self._drop_guide_segments_for_mime(md)
        detail = self._drop_guide_detail_for_mime(md)
        if (
            x != self._drop_guide_x
            or label != self._drop_guide_label
            or detail != self._drop_guide_detail
            or width_px != self._drop_guide_width_px
            or segments != self._drop_guide_segments
        ):
            self._drop_guide_x = x
            self._drop_guide_label = label
            self._drop_guide_detail = detail
            self._drop_guide_width_px = width_px
            self._drop_guide_segments = segments
            self.update()

    def _clear_drop_guide(self) -> None:
        if (
            self._drop_guide_x is not None
            or self._drop_guide_label
            or self._drop_guide_detail
            or self._drop_guide_width_px
            or self._drop_guide_segments
        ):
            self._drop_guide_x = None
            self._drop_guide_label = ""
            self._drop_guide_detail = ""
            self._drop_guide_width_px = 0
            self._drop_guide_segments = []
            self.update()

    @staticmethod
    def _ar_pbr_paths_from_mime(md: QMimeData) -> list[Path]:
        return _shared_ar_pbr_paths_from_mime(md)

    @staticmethod
    def _mmd_paths_from_mime(md: QMimeData) -> list[Path]:
        return _shared_mmd_paths_from_mime(md)



    def dragLeaveEvent(self, event) -> None:
        if self._drop_target_clip_id is not None:
            self._drop_target_clip_id = None
            self.update()
        self._clear_effect_drop_target()
        self._clear_drop_guide()
        super().dragLeaveEvent(event)

    # 30px snap radius for clip right-edge detection during transition drag
    _TRANSITION_DROP_SNAP_PX = 30

    def _update_transition_drop_target(self, pos: QPoint) -> None:
        """Find the clip whose right edge is closest to ``pos`` within the
        snap radius, store its id in ``_drop_target_clip_id``, and repaint."""
        best_id: int | None = None
        best_dist = self._TRANSITION_DROP_SNAP_PX + 1
        for clip in (getattr(self.track, "clips", None) or []):
            cr = self._clip_rect(clip)
            if cr.width() <= 0:
                continue
            dist = abs(pos.x() - cr.right())
            if dist < best_dist and cr.top() <= pos.y() <= cr.bottom():
                best_dist = dist
                best_id = int(clip.id)
        if best_id != self._drop_target_clip_id:
            self._drop_target_clip_id = best_id
            self.update()





from app import timeline_track_row_events as _timeline_track_row_events
from app import timeline_track_row_paint as _timeline_track_row_paint
from app import timeline_track_row_chrome as _timeline_track_row_chrome

TrackRow.mousePressEvent = _timeline_track_row_events.mousePressEvent
TrackRow.mouseMoveEvent = _timeline_track_row_events.mouseMoveEvent
TrackRow.mouseReleaseEvent = _timeline_track_row_events.mouseReleaseEvent
TrackRow.dragEnterEvent = _timeline_track_row_events.dragEnterEvent
TrackRow.dragMoveEvent = _timeline_track_row_events.dragMoveEvent
TrackRow.dropEvent = _timeline_track_row_events.dropEvent
TrackRow.paintEvent = _timeline_track_row_paint.paintEvent
TrackRow._paint_clip_length_chrome = _timeline_track_row_chrome._paint_clip_length_chrome
TrackRow._on_context_menu = _timeline_track_row_chrome._on_context_menu
TrackRow._show_speed_menu = _timeline_track_row_chrome._show_speed_menu
TrackRow._show_transition_menu = _timeline_track_row_chrome._show_transition_menu
TrackRow._paint_zoom_actor = _timeline_track_row_chrome._paint_zoom_actor
TrackRow._paint_typography_actor = _timeline_track_row_chrome._paint_typography_actor
