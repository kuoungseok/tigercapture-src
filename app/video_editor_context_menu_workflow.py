from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox, QMenu

from app.i18n import tr
from app.icons import app_icon
from app.video_editor_nested_sequence import NestedSequenceEditorDialog


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
    """Right-click on empty row area ??offer row-level actions only."""
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
    """Right-click on a specific clip ??per-clip actions."""
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
        self._remove_clip_from_waveform_jobs(clip)
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


def _on_clip_badge_action_requested(self, track_id: int, clip_id: int, action: str) -> None:
    track = self._find_track(track_id)
    if track is None:
        return
    clip = next((c for c in getattr(track, "clips", []) if int(c.id) == int(clip_id)), None)
    if clip is None:
        return
    self._select_workflow_video_clip(track, clip)
    action = str(action or "inspect").casefold()
    panel = getattr(self, "_workbench_panel", None)
    if panel is not None and hasattr(panel, "_set_inspector_tab"):
        try:
            panel._set_inspector_tab("fx")
        except Exception:
            pass
    if action == "transition":
        t_ms = int(getattr(clip, "transition_out_ms", 0) or 0)
        focus_ms = max(
            int(getattr(clip, "timeline_in_ms", 0) or 0),
            int(getattr(clip, "timeline_out_ms", 0) or 0) - max(120, t_ms // 2),
        )
        self._focus_preview_at_workflow_ms(focus_ms, track=track)
        self._flash_status(tr("veditor.clip_badge.status.transition_focused"))
        return
    if action == "title":
        focus_ms = self._first_overlapping_actor_ms(
            getattr(track, "typography_actors", []) or [],
            clip,
        )
        self._focus_preview_at_workflow_ms(focus_ms, track=track)
        self._flash_status(tr("veditor.clip_badge.status.title_focused"))
        return
    if action == "motion":
        focus_ms = self._first_overlapping_actor_ms(
            getattr(track, "zoom_actors", []) or [],
            clip,
        )
        self._focus_preview_at_workflow_ms(focus_ms, track=track)
        self._flash_status(tr("veditor.clip_badge.status.motion_focused"))
        return
    if action == "nested":
        self._flash_status(tr("veditor.clip_badge.status.nested_selected"))
        return
    self._refresh_workbench()
    self._flash_status(tr("veditor.clip_badge.status.fx_focused"))


def _on_clip_badge_context_menu(self, track_id: int, clip_id: int, action: str, global_pos: "QPoint") -> None:
    track = self._find_track(track_id)
    if track is None:
        return
    clip = next((c for c in getattr(track, "clips", []) if int(c.id) == int(clip_id)), None)
    if clip is None:
        return
    self._select_workflow_video_clip(track, clip)
    action = str(action or "inspect").casefold()
    menu = QMenu(self)
    command_by_action = {}
    for row in self._clip_badge_menu_model(clip, action):
        act = menu.addAction(str(row.get("label") or row.get("id") or "Action"))
        act.setEnabled(bool(row.get("enabled", True)))
        command_by_action[act] = str(row.get("id") or "")
    chosen = menu.exec(global_pos)
    if chosen is None:
        return
    self._run_clip_badge_menu_action(track, clip, action, command_by_action.get(chosen, ""))


@staticmethod
def _first_overlapping_actor_ms(actors, clip) -> int:
    clip_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
    clip_end = int(getattr(clip, "timeline_out_ms", clip_start) or clip_start)
    for actor in actors or []:
        start = int(getattr(actor, "start_ms", 0) or 0)
        end = int(getattr(actor, "end_ms", start) or start)
        if clip_start < end and start < clip_end:
            return max(0, start)
    return max(0, clip_start)


def _on_video_clip_context_menu(self, track_id: int, clip_id: int, global_pos: "QPoint") -> None:
    """Right-click on a video clip ??show effects + standard options."""
    track = self._find_track(track_id)
    if track is None:
        return
    clip = next((c for c in getattr(track, "clips", []) if c.id == clip_id), None)
    if clip is None:
        return
    self._select_workflow_video_clip(track, clip)
    menu = QMenu(self)
    fx_act = menu.addAction(app_icon("color", size=16), "?대┰ ?댄럺??..")
    focus_fx_act = menu.addAction("FX stack in Workbench")
    has_active_fx = self._clip_has_active_fx(clip)
    has_disabled_fx = self._clip_has_disabled_fx(clip)
    toggle_fx_act = menu.addAction("Enable Clip FX" if has_disabled_fx and not has_active_fx else "Disable Clip FX")
    toggle_fx_act.setEnabled(bool(has_active_fx or has_disabled_fx))
    clear_fx_act = menu.addAction("Clear Clip FX")
    clear_fx_act.setEnabled(bool(has_active_fx or has_disabled_fx))
    clear_transition_act = menu.addAction("Clear Transition")
    clear_transition_act.setEnabled(bool(str(getattr(clip, "transition_out_type", "") or "")))
    edit_nested_act = None
    open_nested_act = None
    if bool(getattr(clip, "is_nested_sequence", False)):
        menu.addSeparator()
        edit_nested_act = menu.addAction("Edit nested sequence...")
        open_nested_act = menu.addAction("Expand nested sequence")
    menu.addSeparator()
    extract_audio_act = menu.addAction(tr("veditor.menu.extract_audio"))
    extract_audio_act.setEnabled(
        getattr(clip, "source_path", None) is not None
        or getattr(track, "source_path", None) is not None
    )
    menu.addSeparator()
    split_act = menu.addAction(app_icon("scissors", size=16), "?ш린??遺꾪븷")
    del_act = menu.addAction(app_icon("trash", size=16), "??젣")
    chosen = menu.exec(global_pos)
    if chosen is fx_act:
        self._open_clip_effects(track, clip)
    elif chosen is focus_fx_act:
        self._on_clip_badge_action_requested(track_id, clip_id, "fx")
    elif chosen is toggle_fx_act:
        if has_active_fx:
            self._set_clip_fx_enabled(track, clip, False)
        else:
            self._set_clip_fx_enabled(track, clip, True)
    elif chosen is clear_fx_act:
        if not self._clear_clip_fx(track, clip):
            self._flash_status("Selected clip has no clip FX to clear")
        else:
            self._flash_status("Cleared clip FX")
    elif chosen is clear_transition_act:
        if not self._clear_clip_transition(track, clip):
            self._flash_status("Selected clip has no transition to clear")
    elif edit_nested_act is not None and chosen is edit_nested_act:
        self._edit_nested_sequence_clip(track, clip)
    elif open_nested_act is not None and chosen is open_nested_act:
        self._open_nested_sequence_for_edit(track, clip)
    elif chosen is extract_audio_act:
        self._extract_audio_from_video_selection(track, clip)
    elif chosen is split_act:
        self._blade_at_playhead(track_id=track_id)
    elif chosen is del_act:
        self._delete_selected_clips()


def _extract_audio_from_video_selection(self, track, clip=None) -> None:
    params: dict[str, object] = {
        "track_id": int(getattr(track, "id", 0) or 0),
        "link": True,
        "name": "Extracted Audio",
    }
    if clip is not None:
        params["clip_id"] = int(getattr(clip, "id", 0) or 0)
    result = self._ensure_python_action_registry().execute(
        "audio.extract_from_video",
        params,
    ).to_dict()
    if not result.get("ok"):
        QMessageBox.warning(
            self,
            tr("veditor.title"),
            str(result.get("error") or result.get("message") or tr("veditor.menu.extract_audio_none")),
        )
        return
    data = result.get("result") if isinstance(result.get("result"), dict) else {}
    lane_id = data.get("audio_track_id") if isinstance(data, dict) else None
    self._flash_status(f"Audio extracted{f' to track {lane_id}' if lane_id else ''}")


def _edit_nested_sequence_clip(self, track, clip) -> None:
    dlg = NestedSequenceEditorDialog(clip, self)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    track.clips.sort(key=lambda c: int(c.timeline_in_ms))
    track.clips_explicit = True
    row = self._track_rows.get(track.id)
    if row is not None:
        row._recalc_width()
        row.update()
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    self._register_change("edit nested sequence")
    self._flash_status("Nested sequence updated")


def _open_clip_effects(self, track, clip) -> None:
    """Open the ClipEffectsDialog for the given clip."""
    try:
        from app.clip_effects_dialog import ClipEffectsDialog
    except ImportError:
        return

    def refresh():
        self._player.refresh_current_frame()

    dlg = ClipEffectsDialog(clip, refresh_fn=refresh, parent=self)
    dlg.effects_changed.connect(refresh)
    dlg.exec()
    row = getattr(self, "_track_rows", {}).get(getattr(track, "id", None))
    if row is not None:
        row.update()
    self._refresh_workbench()
    self._refresh_preview_soft(track)
    self._register_change("clip effect changed")


def _on_track_context_menu(self, track_id: int, global_pos: QPoint) -> None:
    self._set_active_track(track_id)
    track = self._find_track(track_id)
    if track is None:
        return

    menu = QMenu(self)
    # DaVinci-style: no "Load video..." menu entry on the track
    # itself. External files always go through the Media Pool ??
    # either via the pool's right-click "Load video files??, a
    # drop on the pool, or by dragging an OS file straight onto
    # the track (the existing dropEvent handles that path).

    # Option C: blade at playhead replaces the legacy
    # "cut selection" entry (which depended on Shift+drag selection
    # that no longer exists).
    act_blade = menu.addAction(tr("veditor.menu.blade_at_playhead"))
    act_blade.setEnabled(bool(getattr(track, "clips", None)))

    # Ripple delete the currently-selected clip(s), if any.
    act_ripple = menu.addAction(tr("veditor.menu.ripple_delete"))
    act_ripple.setEnabled(bool(self._selected_clips))

    edge_summary = self._timeline_edge_issue_summary(
        [track],
        getattr(self, "_project_settings", None),
    )
    act_clean_edges = menu.addAction("Clean 1-frame gaps/overlaps")
    act_clean_edges.setEnabled(
        int(edge_summary.get("auto_fixable_count", 0) or 0) > 0
        and not bool(getattr(track, "locked", False))
    )
    act_clean_edges.setToolTip(
        "Close one-frame gaps and trim one-frame overlaps on this track."
    )

    menu.addSeparator()
    act_extract_audio = menu.addAction(tr("veditor.menu.extract_audio"))
    # Enable if ANY clip in this track has a source (works for multi-source tracks)
    has_any_source = (track.source_path is not None) or any(
        getattr(c, "source_path", None) is not None
        for c in getattr(track, "clips", [])
    )
    act_extract_audio.setEnabled(has_any_source)

    # Audio link menu item ??visible when exactly one video clip is selected.
    act_audio_link = None
    _link_clip = None
    if len(self._selected_clips) == 1:
        sel_tid, sel_cid = self._selected_clips[0]
        sel_track = self._find_track(sel_tid)
        if sel_track is not None:
            _link_clip = next(
                (c for c in getattr(sel_track, "clips", []) if c.id == sel_cid),
                None,
            )
        if _link_clip is not None and self._audio_tracks:
            menu.addSeparator()
            is_linked = getattr(_link_clip, "linked_audio_id", None) is not None
            link_label = "?ㅻ뵒??留곹겕 ?댁젣" if is_linked else "?ㅻ뵒??留곹겕"
            act_audio_link = menu.addAction(link_label)

    menu.addSeparator()
    # Track reorder
    idx = self._tracks.index(track) if track in self._tracks else -1
    act_move_up = menu.addAction("?꾨줈 ?대룞 (?덉씠???щ━湲?")
    act_move_up.setEnabled(idx > 0)
    act_move_down = menu.addAction("?꾨옒濡??대룞 (?덉씠???대━湲?")
    act_move_down.setEnabled(0 <= idx < len(self._tracks) - 1)

    menu.addSeparator()
    act_delete = menu.addAction(tr("veditor.menu.delete_track"))
    act_delete.setEnabled(len(self._tracks) > 1 or bool(self._audio_tracks))

    chosen = menu.exec(global_pos)
    if chosen is None:
        return
    if act_audio_link is not None and chosen is act_audio_link:
        if _link_clip is not None:
            self._toggle_audio_link(sel_track, _link_clip)
        return
    if chosen is act_blade:
        self._blade_at_playhead()
    elif chosen is act_ripple:
        self._delete_selected_clips()
    elif chosen is act_clean_edges:
        self._cleanup_timeline_micro_edges(track_id)
    elif chosen is act_move_up:
        self._move_track(track_id, -1)
    elif chosen is act_move_down:
        self._move_track(track_id, +1)
    elif chosen is act_extract_audio:
        target_clip = None
        if len(self._selected_clips) == 1:
            sel_tid, sel_cid = self._selected_clips[0]
            if int(sel_tid) == int(track_id):
                target_clip = next(
                    (
                        c for c in getattr(track, "clips", []) or []
                        if int(getattr(c, "id", -1)) == int(sel_cid)
                    ),
                    None,
                )
        if target_clip is None:
            for candidate in getattr(track, "clips", []) or []:
                if getattr(candidate, "source_path", None) is not None:
                    target_clip = candidate
                    break
        self._extract_audio_from_video_selection(track, target_clip)
    elif chosen is act_delete:
        self._delete_track(track_id)
