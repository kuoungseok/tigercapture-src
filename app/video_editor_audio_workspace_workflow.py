from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from app.audio_tracks import AudioClip, AudioTrack, probe_audio_duration_ms
from app.i18n import tr
from app.video_editor_audio_widgets import SoundEditorWindow, _block_signals
from app.video_editor_transport_workflow import _format_ms


def _next_clip_id(self) -> int:
    cid = getattr(self, "_next_audio_clip_id", 1)
    self._next_audio_clip_id = cid + 1
    return cid


def _find_audio_track(self, track_id: int) -> AudioTrack | None:
    return next((track for track in self._audio_tracks if track.id == track_id), None)


def _find_audio_clip(self, track_id: int, clip_id: int) -> tuple[AudioTrack | None, AudioClip | None]:
    track = self._find_audio_track(track_id)
    if track is None:
        return None, None
    return track, next((clip for clip in track.clips if clip.id == clip_id), None)


def _on_audio_track_changed(self, tid: int) -> None:
    track = self._find_audio_track(tid)
    if track is not None:
        self._audio_mixer.update_track(track)
    self._refresh_player_tracks()


def _on_audio_mixer_visibility_changed(self, visible: bool) -> None:
    self._refresh_timeline_mixer_geometry(visible)
    for attr in ("audio_mixer_tl_btn", "_audio_workspace_mixer_btn"):
        btn = getattr(self, attr, None)
        if btn is not None:
            with _block_signals(btn):
                btn.setChecked(bool(visible))


def _on_mixer_pan_changed(self, track_id: int, pan: float) -> None:
    track = self._find_audio_track(track_id)
    if track is None:
        return
    track.pan = max(-1.0, min(1.0, pan))
    self._audio_mixer.update_track(track)


def _on_mixer_mute_changed(self, track_id: int, muted: bool) -> None:
    track = self._find_audio_track(track_id)
    if track is None:
        return
    track.muted = bool(muted)
    self._audio_mixer.update_track(track)
    if hasattr(self, "_audio_mixer_panel"):
        self._audio_mixer_panel.sync_track_mute(track_id, track.muted)
    self._refresh_player_tracks()


def _on_mixer_solo_changed(self, track_id: int, solo: bool) -> None:
    track = self._find_audio_track(track_id)
    if track is None:
        return
    track.solo = bool(solo)
    self._audio_mixer.update_track(track)
    if hasattr(self, "_audio_mixer_panel"):
        self._audio_mixer_panel.sync_track_solo(track_id, track.solo)
        pos = self._player.position() if hasattr(self, "_player") else 0
        self._audio_mixer_panel.update_levels(pos, self._audio_tracks)
        self._audio_mixer_panel.update_scopes(pos, self._audio_tracks)
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
    self._try_apply_startup_template_if_ready("audio import")


def _on_audio_clip_selection_changed(
    self, tid: int, cid: int, _start: int, _end: int
) -> None:
    # Take ownership of the ants ??clears video ants globally.
    # Use globals() directly so we mutate THIS module's namespace,
    # not a potentially-stale re-import reference.
    import sys as _sys
    _sys.modules[__name__]._ANTS_OWNER = "audio"
    if self._selected_clips:
        self._selected_clips.clear()
        for row in self._track_rows.values():
            row.set_selected_clip_ids(set())
        self._update_timeline_status()
    # Trigger a repaint on all video track rows so the ants disappear there.
    for row in self._track_rows.values():
        row.update()
    # Row persists the selection on the clip itself; we just push
    # the clip's metadata into the right-dock inspector so the
    # user has a contextual readout.
    if not hasattr(self, "_workbench_panel"):
        return
    track = self._find_audio_track(tid)
    if track is None:
        self._workbench_panel.clear()
        return
    clip = next((c for c in track.clips if c.id == cid), None)
    if clip is None:
        self._workbench_panel.clear()
        return
    self._workbench_panel.set_audio_clip(track, clip)
    self._refresh_audio_workspace_panel()


def _open_sound_editor(self, tid: int, cid: int) -> None:
    track, clip = self._find_audio_clip(tid, cid)
    if clip is None or clip.source_path is None:
        return
    from app.sound_editor_panel import SoundEditorDockWindow

    editor = SoundEditorDockWindow(
        clip,
        track=track,
        mixer_tracks=list(getattr(self, "_audio_tracks", []) or []),
        parent=self,
    )
    editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    if not hasattr(self, "_sound_editors"):
        self._sound_editors: list[QWidget] = []
    self._sound_editors.append(editor)

    def _refresh_audio_editor_target() -> None:
        row = self._audio_rows.get(getattr(track, "id", None))
        if row is not None:
            row.refresh_from_track()
            row.update()
        try:
            self._audio_mixer.update_track(track)
        except Exception:
            pass
        self._refresh_audio_workspace_panel()

    editor.changed.connect(_refresh_audio_editor_target)
    editor.destroyed.connect(
        lambda _obj, e=editor: (
            self._sound_editors.remove(e) if e in self._sound_editors else None
        )
    )
    editor.show()
    editor.raise_()
    editor.activateWindow()


def _open_advanced_sound_lab(self, track=None, clip=None) -> None:
    if clip is None:
        candidate = self._audio_workspace_candidate()
        if candidate is not None:
            track, clip = candidate
    if clip is None or getattr(clip, "source_path", None) is None:
        return
    editor = SoundEditorWindow(clip, parent=self)
    editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    if not hasattr(self, "_advanced_sound_labs"):
        self._advanced_sound_labs: list[QWidget] = []
    self._advanced_sound_labs.append(editor)

    def _refresh_advanced_audio_target() -> None:
        try:
            if track is not None:
                row = self._audio_rows.get(getattr(track, "id", None))
                if row is not None:
                    row.refresh_from_track()
                    row.update()
                self._audio_mixer.update_track(track)
            self._refresh_audio_workspace_panel()
        except Exception:
            pass

    editor.destroyed.connect(
        lambda _obj, e=editor: (
            self._advanced_sound_labs.remove(e) if e in self._advanced_sound_labs else None
        )
    )
    editor.destroyed.connect(lambda *_args: _refresh_advanced_audio_target())
    editor.show()
    editor.raise_()
    editor.activateWindow()


def _audio_workspace_candidate(self) -> tuple[AudioTrack, AudioClip] | None:
    tids: list[int] = []
    active_tid = getattr(self, "_active_audio_track_id", None)
    if active_tid is not None:
        tids.append(int(active_tid))
    tids.extend(t.id for t in self._audio_tracks if t.id not in tids)

    for tid in tids:
        row = self._audio_rows.get(tid)
        cid = getattr(row, "_active_clip_id", None) if row is not None else None
        if cid is None:
            continue
        track, clip = self._find_audio_clip(tid, int(cid))
        if track is not None and clip is not None and clip.source_path is not None:
            return track, clip

    pos = self._player.position() if hasattr(self, "_player") else 0
    for track in self._audio_tracks:
        for clip in track.clips:
            if clip.source_path is None:
                continue
            if clip.offset_ms <= pos <= clip.offset_ms + clip.effective_length_ms:
                return track, clip

    for track in self._audio_tracks:
        for clip in track.clips:
            if clip.source_path is not None:
                return track, clip
    return None


def _refresh_audio_workspace_panel(self) -> None:
    if not hasattr(self, "_audio_workspace_label"):
        return
    candidate = self._audio_workspace_candidate()
    enabled = candidate is not None
    self._audio_workspace_edit_btn.setEnabled(enabled)
    if candidate is None:
        self._audio_workspace_label.setText("No audio clip selected")
        return
    track, clip = candidate
    name = getattr(clip, "display_name", None) or (
        clip.source_path.name if clip.source_path is not None else "Audio clip"
    )
    self._audio_workspace_label.setText(
        f"{name}\nTrack A{track.id} | {_format_ms(clip.effective_length_ms)}"
    )


def _open_selected_audio_workspace(self) -> None:
    candidate = self._audio_workspace_candidate()
    if candidate is None:
        return
    track, clip = candidate
    self._open_sound_editor(track.id, clip.id)


def _toggle_audio_workspace_mixer(self, checked: bool) -> None:
    if hasattr(self, "audio_mixer_tl_btn"):
        with _block_signals(self.audio_mixer_tl_btn):
            self.audio_mixer_tl_btn.setChecked(bool(checked))
    self._on_audio_mixer_toggled(bool(checked))


def _toggle_audio_workspace_scopes(self, checked: bool) -> None:
    if hasattr(self, "audio_scopes_tl_btn"):
        with _block_signals(self.audio_scopes_tl_btn):
            self.audio_scopes_tl_btn.setChecked(bool(checked))
    self._on_audio_scopes_toggled(bool(checked))


def _on_audio_volume_changed(self, tid: int, _vol: float) -> None:
    track = self._find_audio_track(tid)
    if track is not None:
        self._audio_mixer.update_track(track)
        # Sync mixer panel fader if open
        if hasattr(self, "_audio_mixer_panel"):
            self._audio_mixer_panel.sync_track_volume(tid, track.volume)


def _on_workbench_sound_editor_changed(self) -> None:
    panel = getattr(self, "_workbench_panel", None)
    target = panel.current_target() if panel is not None and hasattr(panel, "current_target") else None
    if target is None:
        return
    if target[0] == "audio":
        track = target[1]
        row = self._audio_rows.get(getattr(track, "id", None))
        if row is not None:
            row.refresh_from_track()
            row.update()
        try:
            self._audio_mixer.update_track(track)
        except Exception:
            pass
        self._refresh_audio_workspace_panel()
    elif target[0] == "audio_source":
        clip = target[1]
        store = getattr(self, "_sound_edit_state_store", None)
        source = getattr(clip, "source_path", None)
        if store is not None and source is not None:
            store.touch(store.media_key(source))


def _on_workbench_sound_editor_mixer_track_changed(self, track) -> None:
    if track is None:
        return
    tid = getattr(track, "id", None)
    row = self._audio_rows.get(tid)
    if row is not None:
        row.refresh_from_track()
        row.update()
    try:
        self._audio_mixer.update_track(track)
    except Exception:
        pass
    panel = getattr(self, "_audio_mixer_panel", None)
    if panel is not None:
        panel.sync_track_volume(tid, getattr(track, "volume", 1.0))
        panel.sync_track_pan(tid, getattr(track, "pan", 0.0))
        panel.sync_track_mute(tid, bool(getattr(track, "muted", False)))
        panel.sync_track_solo(tid, bool(getattr(track, "solo", False)))
        pos = self._player.position() if hasattr(self, "_player") else 0
        panel.update_levels(pos, self._audio_tracks)
        panel.update_scopes(pos, self._audio_tracks)
    self._refresh_player_tracks()
    self._refresh_audio_workspace_panel()


def _on_workbench_music_lab_action_requested(self, action_id: str, params) -> None:
    from app.video_editor_automation_facade import _ensure_python_action_registry

    action = str(action_id or "").strip()
    if not action:
        return
    registry = _ensure_python_action_registry(self)
    action_params = dict(params or {})
    result = registry.execute(action, action_params).to_dict()
    panel = getattr(self, "_workbench_panel", None)
    if not result.get("ok"):
        message = str(result.get("error") or "Music Lab action failed")
        if panel is not None and hasattr(panel, "refresh_music_lab_status"):
            panel.refresh_music_lab_status(message)
        QMessageBox.warning(self, "Music Lab", message)
        return

    payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    composition_id = str(
        payload.get("composition_id")
        or summary.get("id")
        or action_params.get("composition_id")
        or ""
    )
    followups: list[dict] = []
    if action in {"music.regenerate_section", "music.section.set"} and composition_id:
        render_params = {"composition_id": composition_id, "update_existing": True}
        if action_params.get("backend"):
            render_params["backend"] = action_params.get("backend")
        if action_params.get("ai_provider"):
            render_params["ai_provider"] = action_params.get("ai_provider")
            render_params["create_mix"] = True
        if action_params.get("soundfont_path"):
            render_params["soundfont_path"] = action_params.get("soundfont_path")
        if action_params.get("drum_kit_path"):
            render_params["drum_kit_path"] = action_params.get("drum_kit_path")
        if action_params.get("sample_library_policy"):
            render_params["sample_library_policy"] = action_params.get("sample_library_policy")
        render = registry.execute(
            "music.render_to_timeline",
            render_params,
        ).to_dict()
        balance = registry.execute(
            "music.mixer.auto_balance",
            {"composition_id": composition_id},
        ).to_dict()
        followups.extend([render, balance])
        if not render.get("ok"):
            message = str(render.get("error") or "Music Lab timeline update failed")
            if panel is not None and hasattr(panel, "refresh_music_lab_status"):
                panel.refresh_music_lab_status(message)
            QMessageBox.warning(self, "Music Lab", message)
            return
    composition = payload.get("composition") if isinstance(payload.get("composition"), dict) else None
    if composition is not None:
        preview_payload = payload.get("preview") if isinstance(payload.get("preview"), dict) else payload
        if isinstance(preview_payload, dict):
            preview_mix_path = str(preview_payload.get("preview_mix_path") or "")
            if preview_mix_path:
                composition["preview_mix_path"] = preview_mix_path
            stems = preview_payload.get("stems")
            if isinstance(stems, dict) and stems:
                composition["rendered_stems"] = dict(stems)
    if composition is None and composition_id:
        state = registry.execute("music.state", {"composition_id": composition_id}).to_dict()
        followups.append(state)
        state_payload = state.get("result") if isinstance(state.get("result"), dict) else {}
        composition = state_payload.get("composition") if isinstance(state_payload.get("composition"), dict) else None
    if composition is not None and panel is not None and hasattr(panel, "set_music_lab_composition"):
        panel.set_music_lab_composition(composition)

    if action == "music.export_midi":
        message = f"MIDI exported: {payload.get('path', '')}"
    elif action == "music.render.preview":
        message = f"Preview rendered: {payload.get('preview_mix_path', '')}"
    elif action == "music.render_to_timeline":
        message = (
            f"Music updated: {int(payload.get('updated_count') or 0)} updated, "
            f"{int(payload.get('added_count') or 0)} added"
        )
    elif action in {"music.regenerate_section", "music.section.set"}:
        render_payload = {}
        for followup in followups:
            if followup.get("action") == "music.render_to_timeline":
                render_payload = followup.get("result") if isinstance(followup.get("result"), dict) else {}
        message = (
            f"Music edited: {int(render_payload.get('updated_count') or 0)} updated, "
            f"{int(render_payload.get('added_count') or 0)} added"
        )
    else:
        timeline = payload.get("timeline") if isinstance(payload.get("timeline"), dict) else {}
        message = (
            f"Music generated: {int(timeline.get('updated_count') or 0)} updated, "
            f"{int(timeline.get('added_count') or 0)} added"
        )
    if panel is not None and hasattr(panel, "refresh_music_lab_status"):
        panel.refresh_music_lab_status(message)
    try:
        self._refresh_player_tracks()
        self._refresh_audio_workspace_panel()
    except Exception:
        pass


def _on_workbench_music_lab_selection_changed(self, selection) -> None:
    if isinstance(selection, dict):
        self._music_lab_selection = dict(selection)
    else:
        self._music_lab_selection = {}


def _on_audio_scopes_toggled(self, checked: bool) -> None:
    """Show/hide the scopes column inside AudioMixerPanel."""
    if not hasattr(self, "_audio_mixer_panel"):
        return
    if checked:
        if not self._audio_mixer_panel.isVisible():
            self._audio_mixer_panel.setVisible(True)
            self._audio_mixer_panel.rebuild(self._audio_tracks)
            if hasattr(self, "audio_mixer_tl_btn"):
                with _block_signals(self.audio_mixer_tl_btn):
                    self.audio_mixer_tl_btn.setChecked(True)
        self._audio_mixer_panel.set_scopes_visible(True)
        pos = self._player.position() if hasattr(self, "_player") else 0
        self._audio_mixer_panel.update_scopes(pos, self._audio_tracks)
    else:
        self._audio_mixer_panel.set_scopes_visible(False)
    self._refresh_timeline_mixer_geometry(self._audio_mixer_panel.isVisible())
    if hasattr(self, "_audio_workspace_scopes_btn"):
        with _block_signals(self._audio_workspace_scopes_btn):
            self._audio_workspace_scopes_btn.setChecked(bool(checked))


def _on_audio_mixer_toggled(self, checked: bool) -> None:
    """Show/hide the Audio Mixer panel."""
    if not hasattr(self, "_audio_mixer_panel"):
        return
    self._audio_mixer_panel.setVisible(checked)
    if checked:
        self._audio_mixer_panel.rebuild(self._audio_tracks)
        scopes_btn = getattr(self, "audio_scopes_tl_btn", None)
        scopes_on = scopes_btn is not None and scopes_btn.isChecked()
        self._audio_mixer_panel.set_scopes_visible(scopes_on)
    self._refresh_timeline_mixer_geometry(checked)
    if hasattr(self, "_audio_workspace_mixer_btn"):
        with _block_signals(self._audio_workspace_mixer_btn):
            self._audio_workspace_mixer_btn.setChecked(bool(checked))


def _on_mixer_fader_changed(self, track_id: int, volume: float) -> None:
    """Sync a mixer fader move to the track row and audio engine."""
    track = self._find_audio_track(track_id)
    if track is None:
        return
    track.volume = max(0.0, min(1.5, volume))
    row = self._audio_rows.get(track_id)
    if row is not None:
        with _block_signals(row._volume_slider):
            row._volume_slider.setValue(int(round(track.volume * 100)))
    self._audio_mixer.update_track(track)
