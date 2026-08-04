from __future__ import annotations

from PySide6.QtCore import Qt

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
    motion_project_paths_from_mime as _shared_motion_project_paths_from_mime,
    performance_source_paths_from_mime as _shared_performance_source_paths_from_mime,
    timeline_media_paths_from_mime as _shared_timeline_media_paths_from_mime,
)
from app.timeline_cursor import _timeline_tool_cursor
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
from app.typography import TEXT_CLIP_MIME, TextClip
from app.video_editor_preset_cards import (
    EDITOR_PRESET_MIME_TYPE,
    EFFECT_PRESET_MIME_TYPE,
    TITLE_PRESET_MIME_TYPE,
    TRANSITION_MIME_TYPE,
)
from app.timeline_track_row import _append_ux_event

def mousePressEvent(self, event: QMouseEvent) -> None:
    if event.button() != Qt.MouseButton.LeftButton:
        return
    self.clicked.emit(self.track.id)
    # Multi-source tracks have duration_ms == 0 (clips list carries
    # the content).  Guard against truly empty tracks only.
    if self.track.duration_ms <= 0 and not getattr(self.track, "clips", None):
        return
    pos = event.position().toPoint()
    x = pos.x()
    mods = event.modifiers()
    rect = self._timeline_rect()
    if self._playhead_hit(pos):
        self._dragging_playhead = True
        self._drag_start_x = x
        self._drag_start_y = pos.y()
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.position_requested.emit(self.track.id, self._x_to_project_ms(x))
        event.accept()
        return

    if self._edit_tool_mode == "blade" and rect.contains(pos):
        if self._hit_test_clip(pos) is not None:
            self.tool_action_requested.emit(
                self.track.id, "blade", self._x_to_project_ms(x)
            )
        return

    # Zoom actor ??drag (move / resize / fade-in / fade-out) takes
    # priority; the modal opens on double-click only.
    zactor, zoom_zone = self._zoom_at(pos)
    if zactor is not None:
        self._zoom_drag_actor_id = zactor.id
        self._zoom_drag_anchor_ms = self._x_to_ms(x)
        self._zoom_drag_orig_start_ms = int(zactor.start_ms)
        self._zoom_drag_orig_end_ms = int(zactor.end_ms)
        self._zoom_drag_orig_in_ms = int(zactor.zoom_in_ms)
        self._zoom_drag_orig_out_ms = int(zactor.zoom_out_ms)
        if zoom_zone == "left":
            self._zoom_drag_mode = "resize_l"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zoom_zone == "right":
            self._zoom_drag_mode = "resize_r"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zoom_zone == "fade_in":
            self._zoom_drag_mode = "fade_in"
            self.setCursor(Qt.CursorShape.SplitHCursor)
        elif zoom_zone == "fade_out":
            self._zoom_drag_mode = "fade_out"
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self._zoom_drag_mode = "move"
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()
        return

    # Typography actor interactions take priority over everything
    # else ??they sit at the top of the strip and must be movable
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
        self._drag_start_x = x
        self._drag_start_y = pos.y()
        # Notify editor that this actor is selected (for Delete key)
        self.typography_actor_selected.emit(self.track.id, typo_actor.id)
        self.update()
        return

    # CapCut-style transition block: left-click on an existing
    # transition block starts a drag to resize it.
    tr_clip, tr_side = self._transition_handle_at(pos)
    if tr_clip is not None:
        self._dragging_transition = True
        self._drag_transition_clip = tr_clip
        self._drag_transition_side = tr_side
        self._drag_transition_start_ms = int(tr_clip.transition_out_ms)
        self._drag_transition_start_x = x
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        return

    # CapCut-style transition: left-click at the boundary between
    # two adjacent clips inserts a transition using the currently
    # selected type from the TransitionsPanel.
    # Guard: only fire when the click is NOT on any clip body ??
    # if the cursor is already on a clip, the clip-drag path below
    # should win (otherwise short clips and boundary-adjacent clicks
    # silently insert a transition instead of selecting / dragging
    # the second clip).
    boundary_clip = self._clip_at_boundary(pos)
    if boundary_clip is not None and self._hit_test_clip(pos) is None:
        ttype, tms = self._get_current_transition_type()
        boundary_clip.transition_out_type = ttype
        boundary_clip.transition_out_ms = tms
        boundary_clip.transition_preset_meta = {
            "id": str(ttype),
            "name": str(ttype).replace("_", " ").title(),
            "kind": "transition",
        }
        self.update()
        return

    # Fade edge resize takes priority over everything else (audio
    # FadeSegments on video tracks ??keep this for track.fades list).
    fade, side = self._fade_edge_at(x, pos.y())
    if fade is not None:
        self._resizing_fade = fade
        self._resize_side = side
        self._resize_orig_start = fade.start_ms
        self._resize_orig_end = fade.end_ms
        self._drag_start_x = x
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        return

    # Speed edge resize (after fades ??when a fade and a speed
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

    # Clip edge trim / roll edit. Detected AFTER actor/fade/speed
    # handles so those take priority at shared pixels.
    clip_edge_hit = self._clip_edge_at(pos)
    if clip_edge_hit is not None:
        hit_clip, edge_side, roll_neighbour = clip_edge_hit
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        self._clip_trim_clip = hit_clip
        self._clip_trim_side = edge_side
        self._clip_trim_orig_src_in = int(hit_clip.source_in_ms)
        self._clip_trim_orig_src_out = int(hit_clip.effective_source_out_ms)
        self._clip_trim_orig_tl_in = int(hit_clip.timeline_in_ms)
        self._clip_trim_anchor_ms = self._x_to_project_ms(x)
        tool = self._edit_tool_mode
        if (tool == "roll" or ctrl) and roll_neighbour is not None:
            # Roll edit ??boundary between two clips, Ctrl held.
            self._clip_trim_mode = "roll"
            self._clip_trim_roll_right = roll_neighbour
            self._clip_trim_roll_orig_src_in = int(roll_neighbour.source_in_ms)
            self._clip_trim_roll_orig_tl_in = int(roll_neighbour.timeline_in_ms)
        elif (tool == "ripple" or shift) and edge_side == "right":
            self._clip_trim_mode = "ripple_r"
            self._clip_trim_roll_right = None
        elif (tool == "ripple" or shift) and edge_side == "left":
            self._clip_trim_mode = "ripple_l"
            self._clip_trim_roll_right = None
        elif edge_side == "right":
            self._clip_trim_mode = "trim_r"
            self._clip_trim_roll_right = None
        else:
            self._clip_trim_mode = "trim_l"
            self._clip_trim_roll_right = None
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        return

    # Option C: legacy Shift+drag range-select removed. Industry-
    # standard NLEs (DaVinci/Premiere/FCP) use click-to-select on
    # clips and Shift+click for multi-clip add. The Shift modifier
    # is now consumed by the clip-click branch below as the
    # "add to selection" toggle.

    # Drag on the clip body = move the clip on the project timeline
    # (Premiere/DaVinci style). Scrubbing moved to the timeline ruler.
    # Phase 1.5d Step B: hit-test which CLIP the cursor is on so a
    # split (multi-clip) track lets each piece be dragged
    # independently. Single-clip tracks behave identically to before.
    # Option C: emit ``clip_clicked`` / ``empty_area_clicked`` so the
    # editor maintains the project-wide clip selection set.
    if rect.contains(pos):
        hit_clip = self._hit_test_clip(pos)
        mods = event.modifiers()
        shift_held = bool(mods & Qt.KeyboardModifier.ShiftModifier) or bool(
            mods & Qt.KeyboardModifier.ControlModifier
        )
        if hit_clip is not None:
            self.clip_clicked.emit(
                self.track.id, int(hit_clip.id), shift_held,
            )
            badge_action = self._clip_status_action_at(hit_clip, pos)
            if badge_action:
                self.clip_badge_action_requested.emit(
                    self.track.id, int(hit_clip.id), badge_action,
                )
                self.flash_timeline_burst(badge_action, int(hit_clip.timeline_in_ms))
                return
            if self._edit_tool_mode == "slide":
                prev_clip, next_clip = self._slide_neighbours(hit_clip)
                if prev_clip is not None and next_clip is not None:
                    self._slide_drag_clip = hit_clip
                    self._slide_prev_clip = prev_clip
                    self._slide_next_clip = next_clip
                    self._slide_drag_anchor_ms = self._x_to_project_ms(x)
                    self._slide_orig_target_tl_in = int(hit_clip.timeline_in_ms)
                    self._slide_orig_prev_src_out = int(prev_clip.effective_source_out_ms)
                    self._slide_orig_next_src_in = int(next_clip.source_in_ms)
                    self._slide_orig_next_tl_in = int(next_clip.timeline_in_ms)
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                    return
            if self._edit_tool_mode == "slip":
                self._slip_drag_clip = hit_clip
                self._slip_drag_anchor_ms = self._x_to_project_ms(x)
                self._slip_drag_orig_src_in = int(hit_clip.source_in_ms)
                self._slip_drag_orig_src_out = int(hit_clip.effective_source_out_ms)
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                return
            self._dragging_offset = True
            self._drag_start_x = x
            self._drag_start_y = pos.y()
            self._drag_clip_id = int(hit_clip.id)
            self._drag_start_clip_in_ms = int(hit_clip.timeline_in_ms)
            self._drag_start_offset_ms = self.track.offset_ms
            if int(hit_clip.id) in self._selected_clip_ids:
                group_ids = set(self._selected_clip_ids)
            else:
                group_ids = {int(hit_clip.id)}
            self._drag_group_clip_starts = {
                int(c.id): int(c.timeline_in_ms)
                for c in getattr(self.track, "clips", [])
                if int(c.id) in group_ids
            }
            self._drag_last_cross_track_delta_ms = 0
            self._drag_snap_x = None
            self._clear_drag_feedback()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self.empty_area_clicked.emit(self.track.id)

def mouseMoveEvent(self, event: QMouseEvent) -> None:
    # Multi-source tracks have duration_ms == 0 (clips list carries
    # the content).  Guard against truly empty tracks only.
    if self.track.duration_ms <= 0 and not getattr(self.track, "clips", None):
        return
    pos = event.position().toPoint()
    x = pos.x()
    outside_row = not self.rect().adjusted(0, -12, 0, 12).contains(pos)
    vertical_delta = abs(pos.y() - int(getattr(self, "_drag_start_y", pos.y()) or 0))
    horizontal_delta = abs(x - int(getattr(self, "_drag_start_x", x) or 0))
    wants_external_ppt_drag = outside_row and vertical_delta >= 28 and vertical_delta > max(12, horizontal_delta * 0.45)
    if self._dragging_playhead:
        project_ms = self._x_to_project_ms(x)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.position_requested.emit(self.track.id, project_ms)
        event.accept()
        return

    # Typography drag ??active
    if self._typo_drag_mode is not None and self._typo_drag_actor_id is not None:
        actor = None
        for a in self.track.typography_actors:
            if a.id == self._typo_drag_actor_id:
                actor = a
                break
        if actor is None:
            self._typo_drag_mode = None
        else:
            if self._typo_drag_mode == "move" and wants_external_ppt_drag:
                actor.start_ms = int(self._typo_drag_orig_start_ms)
                actor.end_ms = int(self._typo_drag_orig_end_ms)
                self._typo_drag_mode = None
                self._typo_drag_actor_id = None
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                self.update()
                self._start_ppt_typography_drag(actor)
                return
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

    # Zoom actor drag (move / resize_l / resize_r) ??same shape as
    # typography above; just operates on track.zoom_actors.
    if self._zoom_drag_mode is not None and self._zoom_drag_actor_id is not None:
        zactor = None
        for z in self.track.zoom_actors:
            if z.id == self._zoom_drag_actor_id:
                zactor = z
                break
        if zactor is None:
            self._zoom_drag_mode = None
        else:
            delta_ms = self._x_to_ms(x) - self._zoom_drag_anchor_ms
            try:
                from app.screenstudio_polish import screenstudio_apply_manual_zoom_edit

                snap_targets = {0, int(self.track.duration_ms)}
                offset_ms = int(getattr(self.track, "offset_ms", 0) or 0)
                for raw_target in self._extra_snap_targets:
                    snap_targets.add(max(0, int(raw_target) - offset_ms))
                value_ms = None
                if self._zoom_drag_mode == "fade_in":
                    value_ms = self._x_to_ms(x) - int(zactor.start_ms)
                elif self._zoom_drag_mode == "fade_out":
                    value_ms = int(zactor.end_ms) - self._x_to_ms(x)
                result = screenstudio_apply_manual_zoom_edit(
                    zactor,
                    self._zoom_drag_mode,
                    delta_ms=delta_ms,
                    value_ms=value_ms,
                    duration_ms=int(self.track.duration_ms),
                    snap_targets=sorted(snap_targets),
                    orig_start_ms=self._zoom_drag_orig_start_ms,
                    orig_end_ms=self._zoom_drag_orig_end_ms,
                    orig_zoom_in_ms=self._zoom_drag_orig_in_ms,
                    orig_zoom_out_ms=self._zoom_drag_orig_out_ms,
                    project_settings={"screenstudio_zoom_min_duration_ms": self.ZOOM_MIN_DURATION_MS},
                )
                if not result.get("ok"):
                    self._zoom_drag_mode = None
            except Exception:
                self._zoom_drag_mode = None
            self.update()
            self.zoom_changed.emit(self.track.id)
            return

    # Speed edge resize ??active drag
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

    # CapCut-style transition block drag ??resize transition_out_ms.
    if self._dragging_transition and self._drag_transition_clip is not None:
        clip = self._drag_transition_clip
        delta_px = x - self._drag_transition_start_x
        delta_ms = int(delta_px / max(1.0, self._px_per_sec) * 1000)
        if self._drag_transition_side == "right":
            new_ms = max(100, min(3000, self._drag_transition_start_ms + delta_ms))
        else:  # "left" ??dragging left handle shrinks from left
            new_ms = max(100, min(3000, self._drag_transition_start_ms - delta_ms))
        clip.transition_out_ms = new_ms
        self.update()
        return

    # Clip edge trim / roll / ripple trim ??active drag.
    if self._slide_drag_clip is not None:
        mouse_ms = self._x_to_project_ms(x)
        delta = mouse_ms - self._slide_drag_anchor_ms
        if self._apply_slide_delta(delta):
            self._recalc_width()
            self.update()
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
        return

    if self._slip_drag_clip is not None:
        clip = self._slip_drag_clip
        mouse_ms = self._x_to_project_ms(x)
        delta = mouse_ms - self._slip_drag_anchor_ms
        length = max(
            self.CLIP_MIN_DURATION_MS,
            self._slip_drag_orig_src_out - self._slip_drag_orig_src_in,
        )
        source_duration = int(getattr(clip, "source_duration_ms", 0) or 0)
        if source_duration > length:
            new_in = max(
                0,
                min(source_duration - length, self._slip_drag_orig_src_in + delta),
            )
            clip.source_in_ms = int(new_in)
            clip.source_out_ms = int(new_in + length)
            self.update()
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
        return

    if self._clip_trim_clip is not None and self._clip_trim_mode:
        clip = self._clip_trim_clip
        mouse_ms = self._x_to_project_ms(x)
        delta = mouse_ms - self._clip_trim_anchor_ms
        mode = self._clip_trim_mode

        if mode == "trim_r":
            # Ordinary right trim: extend/shrink source_out_ms.
            _prev_out, next_in = self._adjacent_clip_bounds(clip)
            new_src_out = max(
                self._clip_trim_orig_src_in + self.CLIP_MIN_DURATION_MS,
                self._clip_trim_orig_src_out + delta,
            )
            if hasattr(clip, "source_duration_ms") and clip.source_duration_ms > 0:
                new_src_out = min(new_src_out, int(clip.source_duration_ms))
            if next_in is not None:
                max_len = max(
                    self.CLIP_MIN_DURATION_MS,
                    next_in - int(clip.timeline_in_ms),
                )
                new_src_out = min(
                    new_src_out,
                    int(clip.source_in_ms) + max_len,
                )
            clip.source_out_ms = int(new_src_out)
            self._recalc_width()
            self.update()
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
            return

        elif mode == "trim_l":
            # Ordinary left trim: extend/shrink source_in_ms + move timeline_in_ms.
            prev_out, _next_in = self._adjacent_clip_bounds(clip)
            new_src_in = min(
                self._clip_trim_orig_src_out - self.CLIP_MIN_DURATION_MS,
                self._clip_trim_orig_src_in + delta,
            )
            new_src_in = max(0, new_src_in)
            actual_delta = int(new_src_in) - int(self._clip_trim_orig_src_in)
            new_tl_in = max(0, self._clip_trim_orig_tl_in + actual_delta)
            if new_tl_in < prev_out:
                new_tl_in = prev_out
                actual_delta = new_tl_in - int(self._clip_trim_orig_tl_in)
                new_src_in = max(0, self._clip_trim_orig_src_in + actual_delta)
            clip.source_in_ms = int(new_src_in)
            clip.timeline_in_ms = int(new_tl_in)
            self._recalc_width()
            self.update()
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
            return

        elif mode == "ripple_r":
            # Ripple right trim: change duration AND shift all subsequent clips.
            new_src_out = max(
                self._clip_trim_orig_src_in + self.CLIP_MIN_DURATION_MS,
                self._clip_trim_orig_src_out + delta,
            )
            if hasattr(clip, "source_duration_ms") and clip.source_duration_ms > 0:
                new_src_out = min(new_src_out, int(clip.source_duration_ms))
            actual_delta = new_src_out - self._clip_trim_orig_src_out
            clip.source_out_ms = int(new_src_out)
            old_end = self._clip_trim_orig_tl_in + (
                self._clip_trim_orig_src_out - self._clip_trim_orig_src_in
            )
            for other in getattr(self.track, "clips", []):
                if other is clip:
                    continue
                if int(other.timeline_in_ms) >= old_end - 1:
                    other.timeline_in_ms = max(0, int(other.timeline_in_ms) + actual_delta)
            self._recalc_width()
            self.update()
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
            return

        elif mode == "ripple_l":
            # Ripple left trim: change source_in_ms + shift this and all subsequent
            # clips left/right by the same delta (but NOT clips to the left).
            new_src_in = min(
                self._clip_trim_orig_src_out - self.CLIP_MIN_DURATION_MS,
                self._clip_trim_orig_src_in + delta,
            )
            new_src_in = max(0, new_src_in)
            actual_delta = new_src_in - self._clip_trim_orig_src_in
            clip.source_in_ms = int(new_src_in)
            clip.timeline_in_ms = max(0, self._clip_trim_orig_tl_in + actual_delta)
            for other in getattr(self.track, "clips", []):
                if other is clip:
                    continue
                if int(other.timeline_in_ms) >= self._clip_trim_orig_tl_in - 1:
                    other.timeline_in_ms = max(0, int(other.timeline_in_ms) + actual_delta)
            self._recalc_width()
            self.update()
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
            return

        elif mode == "roll":
            # Roll edit: clip A's right edge moves +delta,
            # clip B's left edge moves +delta.  Total duration unchanged.
            roll_b = self._clip_trim_roll_right
            if roll_b is not None:
                new_a_src_out = max(
                    self._clip_trim_orig_src_in + self.CLIP_MIN_DURATION_MS,
                    min(
                        self._clip_trim_orig_src_out + delta,
                        self._clip_trim_orig_src_out
                        + (int(roll_b.effective_source_out_ms) - self._clip_trim_roll_orig_src_in)
                        - self.CLIP_MIN_DURATION_MS,
                    ),
                )
                if hasattr(clip, "source_duration_ms") and clip.source_duration_ms > 0:
                    new_a_src_out = min(new_a_src_out, int(clip.source_duration_ms))
                roll_delta = new_a_src_out - self._clip_trim_orig_src_out
                clip.source_out_ms = int(new_a_src_out)
                new_b_src_in = max(
                    0, self._clip_trim_roll_orig_src_in + roll_delta
                )
                roll_b.source_in_ms = int(new_b_src_in)
                roll_b.timeline_in_ms = max(
                    0, self._clip_trim_roll_orig_tl_in + roll_delta
                )
            self._recalc_width()
            self.update()
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
            return

    # Fade edge resize ??active drag
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

    # Idle hover ??swap cursor when the pointer is over a fade edge
    # or typography actor so the user discovers the affordances.
    # Also update hover-state fields so paint can thicken the edge
    # handles on the thing under the cursor.
    if not (self._dragging_offset or self._dragging_playhead):
        if self._playhead_hit(pos):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self._set_hover_hint("")
            return
        typo_actor, typo_zone = self._typography_at(pos)
        tooltip_clip = self._hit_test_clip(pos)
        tooltip_text = self._clip_effect_tooltip(tooltip_clip) if tooltip_clip is not None else ""
        if tooltip_text != self.toolTip():
            self.setToolTip(tooltip_text)

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
            self._set_hover_hint(
                tr(
                    "veditor.timeline.hover.actor_resize"
                    if typo_zone in ("left", "right")
                    else "veditor.timeline.hover.actor_move"
                ),
                int(getattr(typo_actor, "start_ms", 0) or 0) + int(getattr(self.track, "offset_ms", 0) or 0),
            )
            self.setCursor(
                Qt.CursorShape.SizeHorCursor if typo_zone in ("left", "right")
                else Qt.CursorShape.OpenHandCursor
            )
        else:
            self._hover_typo_actor_id = None
            self._hover_typo_side = ""
            # CapCut-style: show resize cursor when over a transition block
            tr_clip, _tr_side = self._transition_handle_at(pos)
            if tr_clip is not None:
                self._hover_fade = None
                self._hover_fade_side = ""
                self._hover_speed_seg = None
                self._hover_speed_side = ""
                self._set_hover_hint(
                    tr("veditor.timeline.hover.transition_resize"),
                    int(getattr(tr_clip, "timeline_out_ms", 0) or 0),
                )
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                fade, side = self._fade_edge_at(x, pos.y())
                if fade is not None:
                    self._hover_fade = fade
                    self._hover_fade_side = side
                    self._hover_speed_seg = None
                    self._hover_speed_side = ""
                    self._set_hover_hint(
                        tr("veditor.timeline.hover.fade_resize"),
                        int(getattr(fade, "start_ms", 0) or 0) + int(getattr(self.track, "offset_ms", 0) or 0),
                    )
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                else:
                    self._hover_fade = None
                    self._hover_fade_side = ""
                    seg, s_side = self._speed_edge_at(x, pos.y())
                    if seg is not None:
                        self._hover_speed_seg = seg
                        self._hover_speed_side = s_side
                        self._set_hover_hint(
                            tr("veditor.timeline.hover.speed_resize"),
                            int(getattr(seg, "start_ms", 0) or 0) + int(getattr(self.track, "offset_ms", 0) or 0),
                        )
                        self.setCursor(Qt.CursorShape.SizeHorCursor)
                    else:
                        self._hover_speed_seg = None
                        self._hover_speed_side = ""
                        edge = self._clip_edge_at(pos)
                        if edge is not None:
                            edge_clip, edge_side, roll_neighbor = edge
                            self._set_hover_hint(
                                tr(
                                    "veditor.timeline.hover.roll_trim"
                                    if roll_neighbor is not None
                                    else "veditor.timeline.hover.clip_trim"
                                ),
                                int(
                                    getattr(
                                        edge_clip,
                                        "timeline_out_ms" if edge_side == "right" else "timeline_in_ms",
                                        0,
                                    )
                                    or 0
                                ),
                            )
                            self.setCursor(Qt.CursorShape.SizeHorCursor)
                            if (
                                prev_typo_id != self._hover_typo_actor_id
                                or prev_typo_side != self._hover_typo_side
                                or prev_fade is not self._hover_fade
                                or prev_fade_side != self._hover_fade_side
                                or prev_speed is not self._hover_speed_seg
                                or prev_speed_side != self._hover_speed_side
                            ):
                                self.update()
                            return
                        # Show PointingHandCursor near clip boundaries
                        # (teaches users they can click to insert transition)
                        # but only when NOT on a clip body itself ??if the
                        # cursor is already on a clip, OpenHandCursor wins
                        # (clip drag takes priority over transition insert).
                        bnd = self._clip_at_boundary(pos)
                        on_clip = self._hit_test_clip(pos) is not None
                        if bnd is not None and not on_clip:
                            self._set_hover_hint(
                                tr("veditor.timeline.hover.transition_insert"),
                                int(getattr(bnd, "timeline_out_ms", 0) or 0),
                            )
                            hover_cursor = Qt.CursorShape.PointingHandCursor
                        elif on_clip:
                            hit = self._hit_test_clip(pos)
                            hover_cursor = Qt.CursorShape.OpenHandCursor
                            hint_key = "veditor.timeline.hover.clip_move"
                            if self._edit_tool_mode == "slip":
                                hover_cursor = Qt.CursorShape.SizeHorCursor
                                hint_key = "veditor.timeline.hover.slip"
                            elif self._edit_tool_mode == "slide":
                                hover_cursor = Qt.CursorShape.SizeHorCursor
                                hint_key = "veditor.timeline.hover.slide"
                            elif self._edit_tool_mode == "blade":
                                hover_cursor = _timeline_tool_cursor("blade", getattr(self, "_march_offset", 0))
                            self._set_hover_hint(
                                tr(hint_key),
                                int(getattr(hit, "timeline_in_ms", 0) or 0) if hit is not None else None,
                            )
                        else:
                            self._set_hover_hint("")
                            hover_cursor = _timeline_tool_cursor(self._edit_tool_mode, getattr(self, "_march_offset", 0))
                        self.setCursor(hover_cursor)

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
        if self._drag_clip_id is not None and wants_external_ppt_drag:
            clip = self._find_clip_by_id(self._drag_clip_id)
            self._restore_clip_drag_origin()
            self._dragging_offset = False
            self._drag_clip_id = None
            self._drag_group_clip_starts = {}
            self._drag_last_cross_track_delta_ms = 0
            self._drag_snap_x = None
            self._clear_drag_feedback()
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if clip is not None:
                self._start_ppt_timeline_clip_drag(clip)
            return
        delta_px = x - self._drag_start_x
        delta_ms = int(delta_px / self._px_per_sec * 1000)
        new_clip_in = max(0, self._drag_start_clip_in_ms + delta_ms)
        # Phase 1.5d Step B: move the specific clip the user grabbed.
        # When this is the only clip on the track we also keep the
        # legacy ``track.offset_ms`` in lockstep so the export path
        # (which still consults offset + cuts + duration) stays
        # consistent. Multi-clip tracks (post-cut) move just the
        # one clip.
        clip = self._find_clip_by_id(self._drag_clip_id) if self._drag_clip_id is not None else None
        if clip is None:
            # Fallback: clip went away mid-drag (e.g. another cut
            # racing). Keep the old behaviour so the gesture still
            # does something sensible.
            new_offset = max(0, self._drag_start_offset_ms + delta_ms)
            if new_offset != self.track.offset_ms:
                self.track.offset_ms = new_offset
                self._recalc_width()
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
            return
        if len(self._drag_group_clip_starts) > 1:
            snap_px = 8
            snap_ms = max(40, int(snap_px / max(1.0, self._px_per_sec) * 1000))
            group_delta = self._group_drag_delta(delta_ms, snap_ms)
            if group_delta is None:
                return
            incremental_delta = int(group_delta) - int(self._drag_last_cross_track_delta_ms)
            if not self._can_apply_clip_drag_delta(
                self._drag_group_clip_starts.keys(),
                incremental_delta,
            ):
                self._set_drag_feedback(
                    self._blocked_drag_feedback_text(),
                    group_in + group_delta,
                    "blocked",
                )
                self._set_drag_preview(group_in + group_delta, group_out + group_delta, "blocked")
                return
            changed = False
            for c in getattr(self.track, "clips", []):
                cid = int(c.id)
                if cid not in self._drag_group_clip_starts:
                    continue
                old_clip_in = int(c.timeline_in_ms)
                new_group_in = self._drag_group_clip_starts[cid] + group_delta
                if old_clip_in == new_group_in:
                    continue
                c.timeline_in_ms = int(new_group_in)
                changed = True
                if getattr(c, "linked_audio_id", None) is not None:
                    self.clip_drag_delta.emit(
                        self.track.id,
                        int(c.id),
                        int(new_group_in),
                        int(new_group_in - old_clip_in),
                    )
            if changed:
                cross_delta = int(incremental_delta)
                self._drag_last_cross_track_delta_ms = int(group_delta)
                if cross_delta:
                    self.cross_track_group_drag_delta.emit(
                        self.track.id, int(self._drag_clip_id or -1), int(cross_delta)
                    )
                self.track.clips.sort(key=lambda c: int(c.timeline_in_ms))
                self._recalc_width()
                self.update()
                self.offset_changed.emit(self.track.id, self.track.offset_ms)
            return
        # Phase 1.5d post-work: snap to other clip edges + 0 +
        # extra targets (playhead, markers), then refuse drops that
        # would overlap. ``snap_ms`` derives from a fixed pixel
        # tolerance so the stickiness is the same physical width
        # regardless of zoom.
        from app.timeline_model import apply_drag_constraints_detail
        snap_px = 8
        snap_ms = max(40, int(snap_px / max(1.0, self._px_per_sec) * 1000))
        raw_clip_in = int(new_clip_in)
        constraint = apply_drag_constraints_detail(
            self.track.clips,
            clip,
            new_clip_in,
            snap_ms=snap_ms,
            extra_snap_targets=self._extra_snap_targets,
        )
        new_clip_in = int(constraint.timeline_in_ms)
        if bool(getattr(constraint, "snapped", False)):
            snap_target = getattr(constraint, "snap_target_ms", None)
            self._drag_snap_x = self._project_ms_to_x(int(snap_target if snap_target is not None else new_clip_in))
        else:
            self._drag_snap_x = None
        self._set_drag_constraint_feedback(constraint, clip)
        if int(clip.timeline_in_ms) != new_clip_in:
            old_clip_in = int(clip.timeline_in_ms)
            cross_delta = int(new_clip_in) - int(old_clip_in)
            if not self._can_apply_clip_drag_delta({int(clip.id)}, cross_delta):
                self._set_drag_feedback(
                    self._blocked_drag_feedback_text(),
                    new_clip_in,
                    "blocked",
                )
                self._set_drag_preview(
                    new_clip_in,
                    new_clip_in + max(1, int(getattr(clip, "effective_length_ms", 0) or 0)),
                    "blocked",
                )
                return
            clip.timeline_in_ms = new_clip_in
            # source_in/out are untouched ??only the project-time
            # position moves. ``effective_length_ms`` is derived from
            # source_in/out so it stays the same automatically.
            if len(self.track.clips) <= 1:
                self.track.offset_ms = new_clip_in
            self._recalc_width()
            self.update()
            if cross_delta:
                self.cross_track_group_drag_delta.emit(
                    self.track.id, int(clip.id), int(cross_delta)
                )
            self.offset_changed.emit(self.track.id, self.track.offset_ms)
            # Notify editor about clip drag so linked audio can be synced.
            if getattr(clip, "linked_audio_id", None) is not None:
                delta_ms = new_clip_in - old_clip_in
                self.clip_drag_delta.emit(self.track.id, clip.id, new_clip_in, delta_ms)
        return
    if self._dragging_playhead:
        project_ms = self._x_to_project_ms(x)
        self.position_requested.emit(self.track.id, project_ms)

def mouseReleaseEvent(self, event: QMouseEvent) -> None:
    if event.button() != Qt.MouseButton.LeftButton:
        return
    was_dragging_playhead = self._dragging_playhead
    if self._speed_drag_mode is not None:
        # Keep segments ordered for subsequent hit-tests / painting.
        self.track.speed_segments.sort(key=lambda s: s.start_ms)
        self._speed_drag_mode = None
        self._speed_drag_seg = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.speed_changed.emit(self.track.id)
        self.drag_committed.emit(self.track.id)
        self.update()
    if self._typo_drag_mode is not None:
        # Re-sort by start_ms so paint + hit-testing stay consistent.
        self.track.typography_actors.sort(key=lambda c: c.start_ms)
        self._typo_drag_mode = None
        self._typo_drag_actor_id = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.typography_changed.emit(self.track.id)
        self.drag_committed.emit(self.track.id)
        self.update()
    if self._zoom_drag_mode is not None:
        self.track.zoom_actors.sort(key=lambda z: z.start_ms)
        self._zoom_drag_mode = None
        self._zoom_drag_actor_id = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.zoom_changed.emit(self.track.id)
        self.drag_committed.emit(self.track.id)
        self.update()
    if self._dragging_transition:
        self._dragging_transition = False
        self._drag_transition_clip = None
        self._drag_transition_side = ""
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.drag_committed.emit(self.track.id)
        self.update()
    if self._resizing_fade is not None:
        self._resizing_fade = None
        self._resize_side = ""
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.fades_changed.emit(self.track.id)
        self.drag_committed.emit(self.track.id)
    if self._clip_trim_clip is not None:
        # Re-sort clips so timeline order is consistent after trim / roll.
        if hasattr(self.track, "clips"):
            self.track.clips.sort(key=lambda c: int(c.timeline_in_ms))
        self._clip_trim_clip = None
        self._clip_trim_mode = ""
        self._clip_trim_roll_right = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.offset_changed.emit(self.track.id, self.track.offset_ms)
        self.drag_committed.emit(self.track.id)
        self.update()
    if self._slide_drag_clip is not None:
        if hasattr(self.track, "clips"):
            self.track.clips.sort(key=lambda c: int(c.timeline_in_ms))
        self._slide_drag_clip = None
        self._slide_prev_clip = None
        self._slide_next_clip = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.offset_changed.emit(self.track.id, self.track.offset_ms)
        self.drag_committed.emit(self.track.id)
        self.update()
    if self._slip_drag_clip is not None:
        self._slip_drag_clip = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.offset_changed.emit(self.track.id, self.track.offset_ms)
        self.drag_committed.emit(self.track.id)
        self.update()
    if self._dragging_offset:
        _append_ux_event(
            "timeline.drag.release",
            track_id=int(self.track.id),
            feedback=self._drag_feedback_text,
            tone=self._drag_feedback_tone,
            preview_start_ms=self._drag_preview_start_ms,
            preview_end_ms=self._drag_preview_end_ms,
        )
        self._dragging_offset = False
        self._drag_clip_id = None
        self._drag_group_clip_starts = {}
        self._drag_last_cross_track_delta_ms = 0
        self._drag_snap_x = None
        self._clear_drag_feedback()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.offset_changed.emit(self.track.id, self.track.offset_ms)
        # ``drag_committed`` is the user-gesture-end pulse the
        # editor's history stack hooks. Live ``offset_changed``
        # ticks during the drag are intentionally NOT a savepoint.
        self.drag_committed.emit(self.track.id)
        self.update()
    self._dragging_playhead = False
    if was_dragging_playhead:
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

def dragEnterEvent(self, event) -> None:
    md = event.mimeData()
    if md.hasFormat(FADE_MIME_TYPE):
        event.acceptProposedAction()
        return
    if md.hasFormat(TRANSITION_MIME_TYPE):
        event.acceptProposedAction()
        return
    if md.hasFormat(TEXT_CLIP_MIME):
        event.acceptProposedAction()
        return
    if md.hasFormat(SPEED_MIME_TYPE):
        event.acceptProposedAction()
        return
    if md.hasFormat(ZOOM_MIME_TYPE):
        event.acceptProposedAction()
        return
    if md.hasFormat(TITLE_PRESET_MIME_TYPE):
        event.acceptProposedAction()
        return
    if md.hasFormat(EFFECT_PRESET_MIME_TYPE):
        event.acceptProposedAction()
        return
    if md.hasFormat(EDITOR_PRESET_MIME_TYPE):
        event.acceptProposedAction()
        return
    # Accept any media file (video OR audio); the window will route
    # mismatches to the right track type. Qt does not automatically
    # propagate drags from a dropAccepting child to its parent ??
    # so we swallow the event here and emit our own signal.
    if (
        self._ar_pbr_paths_from_mime(md)
        or self._mmd_paths_from_mime(md)
        or _shared_motion_project_paths_from_mime(md)
        or _shared_performance_source_paths_from_mime(md)
        or _shared_timeline_media_paths_from_mime(md)
    ):
        event.acceptProposedAction()
        return
    event.ignore()

def dragMoveEvent(self, event) -> None:
    md = event.mimeData()
    # Transition card: track nearest clip right boundary and highlight it
    if md.hasFormat(TRANSITION_MIME_TYPE):
        event.acceptProposedAction()
        pos = event.position().toPoint()
        self._update_transition_drop_target(pos)
        self._clear_effect_drop_target()
        self._update_drop_guide(pos, md)
        return
    self.dragEnterEvent(event)
    if event.isAccepted():
        if md.hasFormat(EFFECT_PRESET_MIME_TYPE):
            self._update_effect_drop_target(event.position().toPoint(), md)
        else:
            self._clear_effect_drop_target()
        self._update_drop_guide(event.position().toPoint(), md)

def dropEvent(self, event) -> None:
    md = event.mimeData()
    self._clear_drop_guide()
    # Transition card drop: set clip.transition_out_type / _ms on nearest
    # clip right boundary.
    if md.hasFormat(TRANSITION_MIME_TYPE):
        transition_payload = _drop_transition_payload_from_mime(md)
        payload = dict(transition_payload.get("raw") or {})
        ttype = str(transition_payload.get("type") or "dissolve")
        tms = int(transition_payload.get("duration_ms") or 500)
        pos = event.position().toPoint()
        self._update_transition_drop_target(pos)
        target_id = self._drop_target_clip_id
        self._drop_target_clip_id = None
        self.update()
        if target_id is not None:
            clip = self._find_clip_by_id(target_id)
            if clip is not None:
                clip.transition_out_type = ttype
                clip.transition_out_ms = max(50, tms)
                clip.transition_preset_meta = {
                    "id": str(payload.get("preset_id") or payload.get("id") or ttype),
                    "name": str(payload.get("name") or payload.get("preset_name") or ttype),
                    "kind": "transition",
                }
                self.update()
                self.speed_changed.emit(self.track.id)  # triggers repaint chain
        event.acceptProposedAction()
        return
    if md.hasFormat(FADE_MIME_TYPE):
        duration_ms = _drop_fade_duration_from_mime(
            md,
            default_ms=FadeCard.DEFAULT_DURATION_MS,
        )
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
        duration_ms = _drop_text_clip_duration_from_mime(md, default_ms=2000)
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
        speed_payload = _drop_speed_payload_from_mime(
            md,
            default_speed=SpeedCard.DEFAULT_SPEED,
            default_duration_ms=SpeedCard.DEFAULT_DURATION_MS,
        )
        speed = float(speed_payload.get("speed") or SpeedCard.DEFAULT_SPEED)
        dur_ms = int(speed_payload.get("duration_ms") or SpeedCard.DEFAULT_DURATION_MS)
        frame_blend = bool(speed_payload.get("frame_blend"))
        blend_mode = str(speed_payload.get("blend_mode") or "linear")
        dur_ms = max(100, dur_ms)
        center_ms = self._x_to_ms(event.position().toPoint().x())
        start = max(0, center_ms - dur_ms // 2)
        end = min(self.track.duration_ms, start + dur_ms)
        if end <= start:
            return
        # Replace any overlapping speed ranges ??we can't have two
        # different speeds on the same source ms.
        self.track.speed_segments = [
            seg for seg in self.track.speed_segments
            if seg.end_ms <= start or seg.start_ms >= end
        ]
        self.track.speed_segments.append(
            SpeedSegment(start, end, speed,
                         frame_blend=frame_blend, blend_mode=blend_mode)
        )
        self.track.speed_segments.sort(key=lambda s: s.start_ms)
        self.update()
        self.speed_changed.emit(self.track.id)
        self.clicked.emit(self.track.id)
        event.acceptProposedAction()
        return
    # Zoom card drop: add a ZoomActor at the drop position with default
    # duration. Target rect is unset until the user clicks ??modal.
    if md.hasFormat(ZOOM_MIME_TYPE):
        if self.track.duration_ms <= 0:
            return
        dur_ms = _drop_zoom_duration_from_mime(
            md,
            default_ms=ZoomCard.DEFAULT_DURATION_MS,
        )
        dur_ms = max(500, dur_ms)
        center_ms = self._x_to_ms(event.position().toPoint().x())
        start = max(0, center_ms - dur_ms // 2)
        end = min(self.track.duration_ms, start + dur_ms)
        if end <= start:
            return
        new_id = max(
            (z.id for z in self.track.zoom_actors), default=0
        ) + 1
        ramp = max(100, (end - start) // 4)
        actor = ZoomActor(
            id=new_id, start_ms=start, end_ms=end,
            zoom_in_ms=ramp, zoom_out_ms=ramp,
        )
        self.track.zoom_actors.append(actor)
        self.track.zoom_actors.sort(key=lambda z: z.start_ms)
        self.flash_timeline_burst(
            "zoom",
            int(self.track.offset_ms) + (int(start) + int(end)) // 2,
        )
        self.update()
        self.zoom_changed.emit(self.track.id)
        self.clicked.emit(self.track.id)
        # The actor renders with a dashed outline + "no region" label
        # until the user double-clicks it to open the picker ??drop
        # itself shouldn't auto-pop the modal.
        event.acceptProposedAction()
        return
    # Title preset card drop: create a TextClip with preset style +
    # animation settings at the drop position on the typography lane.
    if md.hasFormat(TITLE_PRESET_MIME_TYPE):
        if self.track.duration_ms <= 0:
            event.ignore()
            return
        preset = _drop_title_preset_from_mime(md)
        if preset is None:
            event.ignore()
            return
        duration_ms = max(self.TYPO_MIN_DURATION_MS, int(preset.get("duration_ms", 3000)))
        start = self._x_to_ms(event.position().toPoint().x())
        end = min(self.track.duration_ms, start + duration_ms)
        if end - start < self.TYPO_MIN_DURATION_MS:
            start = max(0, end - self.TYPO_MIN_DURATION_MS)
        if end <= start:
            event.ignore()
            return
        actor = TextClip(start_ms=start, end_ms=end)
        actor.text = str(preset.get("text", ""))
        # Apply style fields from preset
        actor.style.font_size = int(preset.get("font_size", 48))
        actor.style.color = str(preset.get("color", "#ffffff"))
        actor.style.position_x = float(preset.get("x_norm", 0.5))
        actor.style.position_y = float(preset.get("y_norm", 0.5))
        bg = preset.get("bg_color", "")
        if bg:
            actor.style.background_color = str(bg)
        # Apply animation
        actor.animation.in_animation = str(preset.get("preset_id_in", "fade-in"))
        actor.animation.out_animation = str(preset.get("preset_id_out", "fade-out"))
        typo_preset_id = str(preset.get("typography_preset_id", "") or "")
        if typo_preset_id:
            try:
                from app.typo_presets import apply_preset, get_preset
                typo_preset = get_preset(typo_preset_id)
                if typo_preset is not None:
                    apply_preset(actor, typo_preset)
            except Exception:
                pass
        self.track.typography_actors.append(actor)
        self.track.typography_actors.sort(key=lambda c: c.start_ms)
        self.update()
        self.typography_changed.emit(self.track.id)
        self.clicked.emit(self.track.id)
        event.acceptProposedAction()
        return
    if md.hasFormat(EFFECT_PRESET_MIME_TYPE):
        preset = _drop_effect_preset_from_mime(md)
        if preset is None:
            self._clear_effect_drop_target()
            event.ignore()
            return
        clip = self._hit_test_clip(event.position().toPoint())
        if clip is None:
            self._clear_effect_drop_target()
            event.ignore()
            return
        try:
            from app.preset_library import apply_effect_preset_to_clip
            changed = apply_effect_preset_to_clip(clip, preset)
        except Exception:
            changed = False
        if not changed:
            self._clear_effect_drop_target()
            event.ignore()
            return
        self.update()
        self.speed_changed.emit(self.track.id)
        self.clicked.emit(self.track.id)
        clip_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        self.flash_timeline_burst("fx", clip_start)
        self._clear_effect_drop_target()
        event.acceptProposedAction()
        return
    # Any media file dropped onto this row ??let the window route.
    # Video ??fill empty track or add new. Audio ??add new audio track.
    if md.hasFormat(EDITOR_PRESET_MIME_TYPE):
        preset = _drop_editor_preset_from_mime(md)
        if preset is None:
            event.ignore()
            return
        project_ms = self._x_to_ms(event.position().toPoint().x())
        self.editor_preset_dropped.emit(self.track.id, preset, int(project_ms))
        self.clicked.emit(self.track.id)
        event.acceptProposedAction()
        return
    mmd_paths = self._mmd_paths_from_mime(md)
    if mmd_paths:
        self.media_dropped.emit(self.track.id, mmd_paths[0])
        event.acceptProposedAction()
        return
    motion_paths = _shared_motion_project_paths_from_mime(md)
    if motion_paths:
        self.media_dropped.emit(self.track.id, motion_paths[0])
        event.acceptProposedAction()
        return
    ar_paths = self._ar_pbr_paths_from_mime(md)
    if ar_paths:
        self.ar_pbr_asset_dropped.emit(
            ar_paths[0],
            int(self._x_to_ms(event.position().toPoint().x())),
        )
        event.acceptProposedAction()
        return
    perf_paths = _shared_performance_source_paths_from_mime(md)
    if perf_paths:
        self.performance_source_dropped.emit(
            perf_paths[0],
            int(self._x_to_ms(event.position().toPoint().x())),
        )
        event.acceptProposedAction()
        return
    media_paths = _shared_timeline_media_paths_from_mime(md)
    if media_paths:
        self.media_dropped.emit(self.track.id, media_paths[0])
        event.acceptProposedAction()
        return
    event.ignore()
