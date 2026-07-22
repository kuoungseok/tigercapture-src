from __future__ import annotations

from app.i18n import tr
from app.timeline_ruler import (
    DEFAULT_PX_PER_SEC,
    MAX_PX_PER_SEC,
    MIN_PX_PER_SEC,
    TimelineRuler,
)
from app.video_editor_typography_dialogs import ZoomActorDialog
from app.video_editor_audio_widgets import _block_signals
from app.video_editor_transport_workflow import _timeline_frame_ms


def _format_ms(ms: int) -> str:
    ms = max(0, int(ms))
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _is_text_focus(self) -> bool:
    """Return True when a text-entry widget owns focus.

    Global editing shortcuts should not fight normal typing in subtitle
    dialogs, workbench panels, node-rename modals, and spin boxes.
    """
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QLineEdit,
        QPlainTextEdit,
        QSpinBox,
        QTextEdit,
    )

    fw = QApplication.focusWidget()
    if fw is None:
        return False
    return isinstance(fw, (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox))


def _clamp_timeline_zoom_px(px_per_sec: float) -> float:
    try:
        value = float(px_per_sec)
    except Exception:
        value = DEFAULT_PX_PER_SEC
    return max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, value))


def _change_zoom(self, factor: float) -> None:
    self._set_timeline_zoom_px(self._px_per_sec * float(factor))


def _format_zoom(self) -> str:
    return f"{self._px_per_sec:.0f} px/s"


def _shortcut_zoom_in(self) -> None:
    if self._is_text_focus():
        return
    if self._set_timeline_zoom_px(self._px_per_sec * 1.5):
        self._ensure_playhead_visible()
        self._flash_status(f"Timeline zoom: {self._format_zoom()}")


def _shortcut_zoom_out(self) -> None:
    if self._is_text_focus():
        return
    if self._set_timeline_zoom_px(self._px_per_sec / 1.5):
        self._ensure_playhead_visible()
        self._flash_status(f"Timeline zoom: {self._format_zoom()}")


def _shortcut_zoom_fit(self) -> None:
    if self._is_text_focus():
        return
    before = float(self._px_per_sec)
    self._zoom_fit()
    if abs(float(self._px_per_sec) - before) >= 0.001:
        self._ensure_playhead_visible()
        self._flash_status(f"Timeline fit: {self._format_zoom()}")


def _mark_in_at_playhead(self) -> None:
    self._set_global_in(self._player.position())


def _mark_out_at_playhead(self) -> None:
    self._set_global_out(self._player.position())


def _speed_at(track, pos_ms: int) -> float:
    for segment in track.speed_segments:
        if segment.contains(pos_ms):
            return segment.speed
    return 1.0


def _timeline_nudge_step_ms(
    settings: dict | None = None,
    *,
    shift: bool = False,
    ctrl: bool = False,
) -> int:
    if shift:
        return 1000
    frame_ms = _timeline_frame_ms(settings)
    return frame_ms * 10 if ctrl else frame_ms


def _on_timeline_tool_action(self, track_id: int, tool: str, project_ms: int) -> None:
    if tool == "blade":
        self._blade_track_at_ms(track_id, project_ms)


def _set_timeline_tool_mode(self, mode: str) -> None:
    if self._is_text_focus():
        return
    mode = str(mode or "select")
    if mode not in {"select", "blade", "ripple", "roll", "slip", "slide"}:
        mode = "select"
    self._timeline_tool_mode = mode
    for key, btn in getattr(self, "_timeline_tool_buttons", {}).items():
        if btn.isChecked() != (key == mode):
            btn.setChecked(key == mode)
    for row in self._track_rows.values():
        row.set_edit_tool_mode(mode)
    self._update_timeline_status()
    btn = getattr(self, "_timeline_tool_buttons", {}).get(mode)
    if btn is not None:
        self._pulse_icon_button(btn, base=18, peak=25, duration=220)
    self._flash_status(f"Timeline tool: {mode.title()}")


def _tick_blade_dash(self) -> None:
    """Advance clip-selection and blade cursor marching-ants animation."""
    self._blade_dash_offset = (self._blade_dash_offset + 1) % 8
    for row in self._track_rows.values():
        clips = getattr(row.track, "clips", None)
        needs_paint = bool(clips and len(clips) >= 2)
        if row._selected_clip_ids:
            row._march_offset = (row._march_offset + 2) % 12
            needs_paint = True
        if getattr(row, "_edit_tool_mode", "") == "blade":
            try:
                row.refresh_edit_tool_cursor(self._blade_dash_offset)
            except Exception:
                pass
        if needs_paint:
            row.update()
    for arow in self._audio_rows.values():
        if arow._active_clip_id is not None:
            arow._march_offset = (arow._march_offset + 2) % 12
            arow.update()


def _on_track_empty_area_clicked(self, track_id: int) -> None:
    if self._selected_clips:
        self._selected_clips.clear()
        self._broadcast_clip_selection()


def _broadcast_clip_selection(self) -> None:
    per_track: dict[int, set[int]] = {}
    for tid, cid in self._selected_clips:
        per_track.setdefault(tid, set()).add(cid)
    for tid, row in self._track_rows.items():
        row.set_selected_clip_ids(per_track.get(tid, set()))
        row.update()
    self._update_timeline_status()
    self._sync_media_pool_featured_to_selected_clip()


def _sync_media_pool_featured_to_selected_clip(self) -> None:
    pool = getattr(self, "_media_pool", None)
    if pool is None or not getattr(self, "_selected_clips", None):
        return
    track, clip = self._selected_video_clip()
    if clip is None:
        return
    path = getattr(clip, "source_path", None) or getattr(track, "source_path", None)
    if path is None:
        return
    try:
        if hasattr(pool, "add_path"):
            pool.add_path(path)
        if hasattr(pool, "select_path"):
            pool.select_path(path)
    except Exception:
        pass


def _refresh_nested_group_counter(self) -> None:
    max_id = 0
    for track in self._tracks:
        for clip in getattr(track, "clips", []) or []:
            gid = getattr(clip, "compound_group_id", None)
            if gid is not None:
                max_id = max(max_id, int(gid))
    self._next_nested_group_id = max(max_id + 1, self._next_nested_group_id)


def _set_global_in(self, ms: int) -> None:
    self._global_in_ms = max(0, int(ms))
    if 0 <= self._global_out_ms < self._global_in_ms:
        self._global_out_ms = self._global_in_ms
    self._timeline_ruler.set_global_markers(self._global_in_ms, self._global_out_ms)


def _set_global_out(self, ms: int) -> None:
    self._global_out_ms = max(0, int(ms))
    if 0 <= self._global_in_ms > self._global_out_ms:
        self._global_in_ms = self._global_out_ms
    self._timeline_ruler.set_global_markers(self._global_in_ms, self._global_out_ms)


def _clear_global_markers(self) -> None:
    self._global_in_ms = -1
    self._global_out_ms = -1
    self._timeline_ruler.set_global_markers(-1, -1)


def _add_marker_at_playhead(self) -> None:
    ms = self._player.position()
    color = self._MARKER_COLORS[len(self._timeline_markers) % len(self._MARKER_COLORS)]
    self._timeline_markers.append({"ms": int(ms), "color": color, "label": ""})
    self._sync_markers_to_ruler()


def _delete_timeline_marker(self, index: int) -> None:
    if 0 <= index < len(self._timeline_markers):
        del self._timeline_markers[index]
        self._sync_markers_to_ruler()


def _sync_markers_to_ruler(self) -> None:
    self._timeline_ruler.set_timeline_markers(self._timeline_markers)
    self._push_snap_targets_to_rows()


def _push_snap_targets_to_rows(self) -> None:
    targets: list[int] = [self._player.position()]
    for marker in self._timeline_markers:
        targets.append(int(marker["ms"]))
    for row in self._track_rows.values():
        row.set_extra_snap_targets(targets)


def _find_zoom_actor(self, track_id: int, zactor_id: int):
    for track in self._tracks:
        if track.id != track_id:
            continue
        for zactor in track.zoom_actors:
            if zactor.id == zactor_id:
                return track, zactor
    return None


def _open_zoom_editor(self, track_id: int, zactor_id: int) -> None:
    found = self._find_zoom_actor(track_id, zactor_id)
    if found is None:
        return
    track, zactor = found
    dlg = ZoomActorDialog(track, zactor, self._player, self)
    if dlg.exec() == dlg.DialogCode.Accepted:
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._on_track_zoom_changed(track_id)


def _show_zoom_menu(self, track_id: int, zactor_id: int, global_pos) -> None:
    from PySide6.QtWidgets import QMenu

    found = self._find_zoom_actor(track_id, zactor_id)
    if found is None:
        return
    track, _zactor = found
    menu = QMenu(self)
    a_edit = menu.addAction(tr("veditor.zoom_menu.edit"))
    menu.addSeparator()
    a_del = menu.addAction(tr("veditor.zoom_menu.delete"))

    chosen = menu.exec(global_pos)
    if chosen is a_edit:
        self._open_zoom_editor(track_id, zactor_id)
    elif chosen is a_del:
        track.zoom_actors = [z for z in track.zoom_actors if z.id != zactor_id]
        row = self._track_rows.get(track_id)
        if row is not None:
            row.update()
        self._on_track_zoom_changed(track_id)


def _candidate_tracks_at(self, project_ms: int) -> list:
    """Return timeline entries whose window contains ``project_ms``."""
    out: list = []
    active = self._active_track()
    if active is not None and active.source_path is not None:
        offset = getattr(active, "offset_ms", 0)
        if offset <= project_ms <= offset + active.duration_ms:
            out.append(("video", active))
    for track in self._tracks:
        if track is active or track.source_path is None:
            continue
        offset = getattr(track, "offset_ms", 0)
        if offset <= project_ms <= offset + track.duration_ms:
            out.append(("video", track))
    for track in self._audio_tracks:
        for clip in track.clips:
            if clip.source_path is None:
                continue
            end = clip.offset_ms + clip.effective_length_ms
            if clip.offset_ms <= project_ms <= end:
                out.append(("audio", track, clip))
    return out


def _set_timeline_zoom_px(self, px_per_sec: float) -> bool:
    new_px = self._clamp_timeline_zoom_px(px_per_sec)
    if abs(new_px - self._px_per_sec) < 0.001:
        return False
    self._px_per_sec = new_px
    for row in self._track_rows.values():
        row.set_px_per_sec(new_px)
    for row in self._audio_rows.values():
        row.set_px_per_sec(new_px)
    self._timeline_ruler.set_px_per_sec(new_px)
    if hasattr(self, "_subtitle_lane"):
        self._subtitle_lane.set_px_per_sec(new_px)
    for row in getattr(self, "_actor_lane_rows", []):
        row.set_px_per_sec(new_px)
    for row in getattr(self, "_live2d_lane_rows", []):
        row.set_px_per_sec(new_px)
    for row in getattr(self, "_ar_pbr_lane_rows", []):
        row.set_px_per_sec(new_px)
    for row in getattr(self, "_mmd_lane_rows", []):
        row.set_px_per_sec(new_px)
    for row in getattr(self, "_motion_lane_rows", []):
        row.set_px_per_sec(new_px)
    self.zoom_label.setText(self._format_zoom())
    self._update_tracks_host_width()
    return True


def _zoom_fit(self) -> None:
    max_span = max((track.offset_ms + track.duration_ms for track in self._tracks), default=0)
    max_span = max(
        max_span,
        max((track.extent_ms() for track in self._audio_tracks), default=0),
        max(
            (clip.end_ms for track in getattr(self, "_spine_actor_tracks", []) for clip in track.clips),
            default=0,
        ),
        max(
            (clip.end_ms for track in getattr(self, "_live2d_actor_tracks", []) for clip in track.clips),
            default=0,
        ),
        max(
            (int(track.get("end_ms", 0) or 0) for track in getattr(self, "_ar_pbr_tracks", []) or []),
            default=0,
        ),
        max(
            (int(track.get("end_ms", 0) or 0) for track in getattr(self, "_mmd_tracks", []) or []),
            default=0,
        ),
        max(
            (int(clip.get("end_ms", 0) or 0) for clip in getattr(self, "_motion_clips", []) or []),
            default=0,
        ),
    )
    if max_span <= 0:
        return
    viewport_w = self._tracks_scroll.viewport().width()
    if viewport_w <= 50:
        return
    target_px = (viewport_w - 40) / (max_span / 1000.0)
    _set_timeline_zoom_px(self, target_px)


def _timeline_clip_bounds_for_review(clip) -> tuple[int, int]:
    start = int(getattr(clip, "timeline_in_ms", getattr(clip, "offset_ms", 0)) or 0)
    end = int(getattr(clip, "timeline_out_ms", 0) or 0)
    if end <= start:
        duration = int(
            getattr(clip, "effective_length_ms", 0)
            or getattr(clip, "duration_ms", 0)
            or getattr(clip, "source_duration_ms", 0)
            or 0
        )
        end = start + max(0, duration)
    return max(0, start), max(start, end)


def _selected_timeline_review_center_ms(self, *, span_ms: int = 12000) -> int:
    player = getattr(self, "_player", None)
    if player is not None and hasattr(player, "position"):
        try:
            pos = int(player.position())
        except Exception:
            pos = 0
        if pos > 0:
            return pos

    selected = list(getattr(self, "_selected_clips", []) or [])
    for track_id, clip_id in selected:
        track = self._find_track(int(track_id))
        if track is None:
            continue
        for clip in list(getattr(track, "clips", []) or []):
            if int(getattr(clip, "id", -1)) != int(clip_id):
                continue
            start, end = _timeline_clip_bounds_for_review(clip)
            length = max(1, end - start)
            if length > int(span_ms * 1.5):
                return start + min(length // 2, max(1000, span_ms // 4))
            return start + length // 2

    track = self._active_track() or next(iter(getattr(self, "_tracks", []) or []), None)
    clips = list(getattr(track, "clips", []) or []) if track is not None else []
    if clips:
        clip = sorted(clips, key=lambda item: int(getattr(item, "timeline_in_ms", 0) or 0))[0]
        start, end = _timeline_clip_bounds_for_review(clip)
        return start + min(max(1000, span_ms // 3), max(0, end - start) // 2)
    return 0


def _apply_timeline_review_framing(
    self,
    checked: bool = False,
    *,
    center_ms: int | None = None,
    span_ms: int = 12000,
    notify: bool = True,
) -> dict[str, object]:
    scroll = getattr(self, "_tracks_scroll", None)
    if scroll is None:
        return {"ok": False, "reason": "timeline_scroll_missing"}
    viewport = scroll.viewport()
    viewport_w = int(viewport.width()) if viewport is not None else 0
    if viewport_w <= 120:
        return {"ok": False, "reason": "timeline_viewport_too_small"}

    span = max(4000, min(24000, int(span_ms or 12000)))
    body_w = max(240, viewport_w - int(getattr(TimelineRuler, "MARGIN", 180)) - 80)
    target_px = body_w / max(0.001, span / 1000.0)
    target_px = max(70.0, min(180.0, target_px))
    changed = _set_timeline_zoom_px(self, target_px)

    if center_ms is None:
        center_ms = _selected_timeline_review_center_ms(self, span_ms=span)
    center = max(0, int(center_ms or 0))

    bar = scroll.horizontalScrollBar()
    content_x = int(TimelineRuler.MARGIN + center / 1000.0 * self._px_per_sec)
    target_scroll = max(0, int(content_x - viewport_w * 0.62))
    if target_scroll <= int(TimelineRuler.MARGIN * 1.25):
        target_scroll = 0
    max_scroll = max(int(bar.maximum() if bar is not None else 0), 0)
    if bar is not None:
        bar.setValue(max(0, min(max_scroll, target_scroll)))

    self._timeline_ruler.update()
    for row in getattr(self, "_track_rows", {}).values():
        row.update()
    for row in getattr(self, "_audio_rows", {}).values():
        row.update()
    if notify:
        self._flash_status(f"Timeline review framing: {self._format_zoom()}")
    return {
        "ok": True,
        "center_ms": center,
        "span_ms": span,
        "px_per_sec": float(self._px_per_sec),
        "scroll": int(bar.value()) if bar is not None else 0,
        "changed": bool(changed),
    }


def _timeline_scroll_for_visible_playhead(
    *,
    current_scroll: int,
    viewport_width: int,
    content_x: int,
    max_scroll: int,
    margin_px: int = 80,
) -> int | None:
    viewport = max(0, int(viewport_width))
    if viewport <= 0:
        return None
    scroll = max(0, int(current_scroll))
    max_scroll = max(0, int(max_scroll))
    margin = max(12, min(int(margin_px), max(12, viewport // 3)))
    x = int(content_x)
    left = scroll + margin
    right = scroll + viewport - margin
    if x < left:
        return max(0, min(max_scroll, x - margin))
    if x > right:
        return max(0, min(max_scroll, x - viewport + margin))
    return None


def _ensure_playhead_visible(self, *, margin_px: int = 80) -> None:
    scroll = getattr(self, "_tracks_scroll", None)
    player = getattr(self, "_player", None)
    if scroll is None or player is None:
        return
    bar = scroll.horizontalScrollBar()
    if bar is None:
        return
    try:
        pos = int(player.position())
    except Exception:
        pos = 0
    x = int(TimelineRuler.MARGIN + max(0, pos) / 1000.0 * self._px_per_sec)
    target = _timeline_scroll_for_visible_playhead(
        current_scroll=bar.value(),
        viewport_width=scroll.viewport().width(),
        content_x=x,
        max_scroll=bar.maximum(),
        margin_px=margin_px,
    )
    if target is not None:
        bar.setValue(int(target))


def _move_track(self, track_id: int, direction: int) -> None:
    """Move a track up (-1) or down (+1) in the layer order."""
    try:
        idx = next(i for i, track in enumerate(self._tracks) if track.id == track_id)
    except StopIteration:
        return
    new_idx = idx + direction
    if new_idx < 0 or new_idx >= len(self._tracks):
        return
    self._tracks[idx], self._tracks[new_idx] = self._tracks[new_idx], self._tracks[idx]
    row_a = self._track_rows.get(self._tracks[idx].id)
    row_b = self._track_rows.get(self._tracks[new_idx].id)
    if row_a is None or row_b is None:
        return
    layout = self._tracks_layout
    idx_a = layout.indexOf(row_a)
    idx_b = layout.indexOf(row_b)
    if idx_a < 0 or idx_b < 0:
        return
    layout.removeWidget(row_a)
    layout.removeWidget(row_b)
    lo, hi = min(idx_a, idx_b), max(idx_a, idx_b)
    if idx_a < idx_b:
        layout.insertWidget(lo, row_b)
        layout.insertWidget(hi, row_a)
    else:
        layout.insertWidget(lo, row_a)
        layout.insertWidget(hi, row_b)
    self._refresh_video_row_lane_indices()
    self._update_tracks_host_width()
    self._refresh_player_tracks()
    self._refresh_pip_panel()
    self._register_change("move track")


def _set_active_track(self, track_id: int) -> None:
    """Set the UI focus target without changing playback composition."""
    if self._active_track_id == track_id:
        self._refresh_proxy_status_ui()
        sync_compare = getattr(self, "_sync_viewer_compare_button", None)
        if callable(sync_compare):
            sync_compare()
        return
    self._active_track_id = track_id
    for tid, row in self._track_rows.items():
        row.set_active(tid == track_id)
    self._refresh_selection_row()
    if hasattr(self, "_color_sliders"):
        self._sync_color_panel()
    self._refresh_workbench()
    if hasattr(self, "_audio_mixer_panel"):
        is_audio = track_id in self._audio_rows
        self._active_audio_track_id = track_id if is_audio else None
        if is_audio and self._audio_mixer_panel.isVisible():
            self._audio_mixer_panel.set_scopes_visible(True)
            pos = self._player.position() if hasattr(self, "_player") else 0
            self._audio_mixer_panel.update_scopes(pos, self._audio_tracks)
            scopes_btn = getattr(self, "audio_scopes_tl_btn", None)
            if scopes_btn is not None and not scopes_btn.isChecked():
                with _block_signals(scopes_btn):
                    scopes_btn.setChecked(True)
    self._refresh_proxy_status_ui()
    sync_compare = getattr(self, "_sync_viewer_compare_button", None)
    if callable(sync_compare):
        sync_compare()


def _update_timeline_status(self) -> None:
    label = getattr(self, "_timeline_status_label", None)
    if label is None:
        return
    mode = str(getattr(self, "_timeline_tool_mode", "select") or "select")
    hints = {
        "select": "Drag clips, Shift-click for multi-select",
        "blade": "Click a clip to split",
        "ripple": "Trim edge and close the gap",
        "roll": "Move a shared cut point",
        "slip": "Change source frames in place",
        "slide": "Move clip between neighbors",
    }
    selected = len(getattr(self, "_selected_clips", None) or [])
    label.setText(
        f"{mode.title()} | {selected} selected | "
        f"{hints.get(mode, hints['select'])} | Alt nudge | Esc reset"
    )
    label.setToolTip(
        "Timeline shortcuts\n"
        "Ctrl+A: select all video timeline clips\n"
        "Ctrl+C / Ctrl+X / Ctrl+V: copy, cut, paste at playhead\n"
        "Ctrl+D: duplicate selected video clips after the selection\n"
        "Esc: return to Select, then clear clip selection\n"
        "Alt+Left/Right: nudge selected clips by one frame\n"
        "Ctrl+Alt+Left/Right: nudge by ten frames\n"
        "Shift+Alt+Left/Right: nudge by one second\n"
        "Up/Down: jump to previous/next edit point\n"
        "J/K/L: reverse jog, pause, forward shuttle\n"
        ", / .: step one frame; Shift+, / Shift+.: ten frames\n"
        "Ctrl+= / Ctrl+- / Ctrl+0: zoom timeline in, out, or fit\n"
        "Shift+Wheel, Middle-drag, or Alt+Left-drag: pan the zoomed timeline\n"
        "Keyboard jumps keep the playhead visible in the timeline viewport\n"
        "V/B/R/N/Y/U: Select, Blade, Ripple, Roll, Slip, Slide"
    )


def _on_clip_clicked(self, track_id: int, clip_id: int, shift_held: bool) -> None:
    """TrackRow forwards a clip click here for single/multi selection."""
    for row in getattr(self, "_live2d_lane_rows", []) or []:
        if getattr(row, "_selected", None) is not None:
            try:
                row._selected = None
                row.update()
            except Exception:
                pass
    import app.video_editor_window as _window_module

    _window_module._ANTS_OWNER = "video"
    key = (int(track_id), int(clip_id))
    track = self._find_track(track_id)
    clicked = None
    if track is not None:
        clicked = next(
            (clip for clip in getattr(track, "clips", []) if int(clip.id) == int(clip_id)),
            None,
        )
    group_id = getattr(clicked, "compound_group_id", None)
    group_keys = [key]
    if group_id is not None and track is not None:
        group_keys = [
            (int(track.id), int(clip.id))
            for clip in getattr(track, "clips", [])
            if getattr(clip, "compound_group_id", None) == group_id
        ] or [key]
    if shift_held:
        if all(item in self._selected_clips for item in group_keys):
            self._selected_clips = [item for item in self._selected_clips if item not in group_keys]
        else:
            for item in group_keys:
                if item not in self._selected_clips:
                    self._selected_clips.append(item)
    else:
        self._selected_clips = list(group_keys)
    self._broadcast_clip_selection()


def _refresh_selection_row(self) -> None:
    track = self._active_track()
    if track is None:
        has_sel = False
        self.selection_label.setText(tr("veditor.no_selection"))
    else:
        has_sel = track.selection_start_ms >= 0 and track.selection_end_ms > track.selection_start_ms
        if has_sel:
            self.selection_label.setText(
                tr(
                    "veditor.selection_range",
                    start=_format_ms(track.selection_start_ms),
                    end=_format_ms(track.selection_end_ms),
                    duration=_format_ms(track.selection_end_ms - track.selection_start_ms),
                )
            )
        else:
            self.selection_label.setText(tr("veditor.no_selection"))
    for btn in self._speed_buttons:
        btn.setEnabled(has_sel)
    self.clear_sel_btn.setEnabled(has_sel)
