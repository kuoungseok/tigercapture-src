from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from app.audio_tracks import (
    AudioClip,
    AudioTrack,
    WaveformExtractor,
    audio_file_cache_key,
    get_cached_spectrum,
    get_cached_waveform,
    probe_audio_duration_ms,
    store_cached_spectrum,
    store_cached_waveform,
)
from app.editor_observability import probe_track_hdr_info as _probe_track_hdr_info
from app.i18n import tr
from app.timeline_track_row import TRACK_V_PADDING, TrackRow
from app.video_editor_audio_widgets import AudioTrackRow, SpectrumExtractor
from app.video_editor_thumbnailing import probe_video_duration_ms
from app.video_track_legacy import VideoTrack, _ensure_video_clips

def _find_track(self, track_id: int) -> VideoTrack | None:
    for track in self._tracks:
        if track.id == track_id:
            return track
    return None


def _active_track(self) -> VideoTrack | None:
    if self._active_track_id is None:
        return None
    return self._find_track(self._active_track_id)


def _add_empty_track(self) -> None:
    tid = self._next_track_id
    self._next_track_id += 1
    track = VideoTrack(id=tid)
    self._tracks.append(track)
    self._insert_track_widget(track)
    if self._active_track_id is None:
        self._set_active_track(tid)


def _add_empty_audio_track(self) -> None:
    tid = self._next_track_id
    self._next_track_id += 1
    track = AudioTrack(id=tid)
    self._audio_tracks.append(track)
    self._insert_audio_track_widget(track)


def _clear_active_selection(self) -> None:
    self._clear_global_markers()
    for track in self._tracks:
        track.selection_start_ms = -1
        track.selection_end_ms = -1
    for track in self._audio_tracks:
        for clip in track.clips:
            clip.selection_start_ms = -1
            clip.selection_end_ms = -1
    for row in self._track_rows.values():
        row.update()
    for row in self._audio_rows.values():
        row.update()
    self._refresh_selection_row()


def _delete_audio_track(self, track_id: int) -> None:
    row = self._audio_rows.pop(track_id, None)
    if row is not None:
        self._tracks_layout.removeWidget(row)
        row.deleteLater()
    track = self._find_audio_track(track_id)
    if track is not None:
        for clip in track.clips:
            self._remove_clip_from_waveform_jobs(clip)
    self._audio_tracks = [track for track in self._audio_tracks if track.id != track_id]
    self._refresh_audio_row_lane_indices()
    self._audio_mixer.remove_track(track_id)
    self._refresh_player_tracks()
    if hasattr(self, "_audio_mixer_panel") and self._audio_mixer_panel.isVisible():
        self._audio_mixer_panel.rebuild(self._audio_tracks)


def _delete_active_track(self, _checked: bool = False) -> None:
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
    self._tracks = [track for track in self._tracks if track.id != track_id]
    extractor = self._extractors.pop(track_id, None)
    if extractor is not None:
        extractor.stop()
    if self._active_track_id == track_id:
        self._active_track_id = None
        if self._tracks:
            self._set_active_track(self._tracks[-1].id)
    self._refresh_video_row_lane_indices()
    self._refresh_player_tracks()


def _find_video_clip(self, track_id: int, clip_id: int):
    track = self._find_track(track_id)
    if track is None:
        return None, None
    for clip in getattr(track, "clips", []) or []:
        try:
            if int(getattr(clip, "id", -1)) == int(clip_id):
                return track, clip
        except Exception:
            continue
    return track, None


def _on_track_position_requested(self, track_id: int, ms: int) -> None:
    if track_id != self._active_track_id:
        self._set_active_track(track_id)
    self._player.set_position(ms)


def _on_track_selection_changed(self, track_id: int, start: int, end: int) -> None:
    if track_id != self._active_track_id:
        self._set_active_track(track_id)
    self._refresh_selection_row()


def _on_track_offset_changed(self, track_id: int, _new_offset_ms: int) -> None:
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    if track_id == self._active_track_id:
        self._refresh_workbench()


def _on_track_fades_changed(self, track_id: int) -> None:
    if track_id == self._active_track_id:
        self._refresh_workbench()


def _on_track_speed_changed(self, track_id: int) -> None:
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    if track_id == self._active_track_id:
        self._refresh_workbench()


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
    self._set_transport_speed_label(1.0)
    row = self._track_rows.get(track.id)
    if row is not None:
        row.update()
    self._refresh_selection_row()


def _on_track_zoom_changed(self, track_id: int) -> None:
    self._update_tracks_host_width()
    self._player.set_position(self._player.position())


def _add_track_with_source(self, path: Path) -> None:
    from app.image_media import is_image_path
    if is_image_path(path):
        from app.video_editor_media_import_controller import add_image_track_with_source

        add_image_track_with_source(self, path)
        return
    self._register_screenstudio_real_recording_candidate(path, reason="track import")
    tid = self._next_track_id
    self._next_track_id += 1
    track = VideoTrack(id=tid, source_path=path)
    # HDR probing is opt-in during interactive import.  It spawns
    # ffmpeg, and doing that while the editor is opening can flash
    # transient helper windows on some Windows setups.
    track.hdr_info = _probe_track_hdr_info(path)
    self._tracks.append(track)
    self._insert_track_widget(track)
    def _start_import_thumbnails() -> None:
        if any(existing is track for existing in getattr(self, "_tracks", []) or []):
            self._start_thumbnail_extraction(track)

    QTimer.singleShot(120, _start_import_thumbnails)
    self._set_active_track(tid)
    # ``_refresh_player_tracks`` opens the cap and sets duration_ms,
    # then rebuilds clips so the new track has the single covering
    # clip Phase 1.5d wants.
    self._refresh_player_tracks(render_immediately=False)
    _ensure_video_clips(track)
    auto_polish_added = 0
    for clip in getattr(track, "clips", []) or []:
        self._load_screenstudio_cursor_sidecar_for_clip(clip)
        auto_polish_added += self._maybe_apply_default_screenstudio_polish_to_clip(
            track,
            clip,
            reason="track import",
        )
    if auto_polish_added > 0:
        self._flash_status(f"Screen Studio polish applied: {auto_polish_added} zoom window(s)")
    # Phase 1.5d Step A regression fix: stored ``clips`` is set
    # AFTER the row was first inserted (which painted with an
    # empty clip list and a 0 duration). Without an explicit
    # repaint here the row stays as the "empty slot" render until
    # thumbnail extraction happens to kick an ``update()`` ??
    # which can be seconds away on long sources, leaving the
    # user staring at a blank track. ``update()`` only ??calling
    # ``_recalc_width`` here triggered a second layout reflow
    # cycle that left the row collapsed in some scenarios.
    row = self._track_rows.get(tid)
    if row is not None:
        row.update()
    self._refresh_visual_preview_after_timeline_change()
    try:
        queue_auto_proxy = getattr(self, "_queue_auto_proxy_generation", None)
        if callable(queue_auto_proxy):
            queue_auto_proxy(paths=[Path(path)])
    except Exception:
        pass
    _is_high_resolution = lambda *_args, **_kwargs: False

    # Proxy: if the source is high-resolution, ask the user once
    # whether to generate a proxy for smoother editing.
    try:
        suppress_prompts = bool(getattr(self, "_suppress_interactive_prompts", False))
        suppress_prompts = suppress_prompts or str(
            os.environ.get("TIGERCAPTURE_SUPPRESS_INTERACTIVE_PROMPTS") or ""
        ).strip().lower() in {"1", "true", "yes", "on", "enabled"}
        if _is_high_resolution(path) and not suppress_prompts:
            w, h = _probe_video_dimensions(path)
            res_label = f"{w}x{h}" if w and h else "4K"
            choice = QMessageBox.question(
                self,
                "프록시 생성",
                f"고해상도 영상을 감지했습니다 ({res_label}).\n"
                f"프록시를 생성하면 편집 성능이 향상됩니다.\n\n"
                f"프록시는 백그라운드에서 생성되며 완료 후 Proxy 버튼으로 전환할 수 있습니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if choice == QMessageBox.StandardButton.Yes:
                self._start_proxy_generation(path)
    except Exception:
        pass

    if str(os.environ.get("TIGERCAPTURE_DIAG_IMPORT") or "").strip().lower() in {"1", "true", "yes", "on"}:
        import sys as _sys
        try:
            print(
                f"[DIAG add_track] tid={tid} "
                f"row_visible={row.isVisible() if row else None} "
                f"row_geo={row.geometry() if row else None} "
                f"row_size={row.size() if row else None} "
                f"clips={len(track.clips)} "
                f"duration_ms={track.duration_ms} "
                f"layout_count={self._tracks_layout.count()} "
                f"layout_indexes=[{','.join(str(self._tracks_layout.indexOf(self._tracks_layout.itemAt(i).widget())) for i in range(self._tracks_layout.count()) if self._tracks_layout.itemAt(i).widget())}]",
                file=_sys.stderr, flush=True,
            )
        except Exception as e:
            print(f"[DIAG add_track] err={e!r}", file=_sys.stderr, flush=True)
    self._try_apply_startup_template_if_ready("video import")


def _insert_track_widget(self, track: VideoTrack) -> None:
    row = TrackRow(track)
    row.installEventFilter(self)
    row.set_px_per_sec(self._px_per_sec)
    row.clicked.connect(self._set_active_track)
    row.position_requested.connect(self._on_track_position_requested)
    row.selection_changed.connect(self._on_track_selection_changed)
    row.context_menu.connect(self._on_track_context_menu)
    row.clip_context_menu.connect(self._on_video_clip_context_menu)
    row.clip_badge_action_requested.connect(self._on_clip_badge_action_requested)
    row.clip_badge_context_menu.connect(self._on_clip_badge_context_menu)
    row.offset_changed.connect(self._on_track_offset_changed)
    row.drag_committed.connect(
        lambda _tid: self._register_change("timeline edit")
    )
    # Option C ??clip-level selection signals.
    row.clip_clicked.connect(self._on_clip_clicked)
    row.empty_area_clicked.connect(self._on_track_empty_area_clicked)
    row.tool_action_requested.connect(self._on_timeline_tool_action)
    row.fades_changed.connect(self._on_track_fades_changed)
    row.speed_changed.connect(self._on_track_speed_changed)
    row.media_dropped.connect(self._on_media_dropped_on_video_row)
    row.ar_pbr_asset_dropped.connect(self._on_ar_pbr_asset_dropped_on_video_row)
    row.performance_source_dropped.connect(self._on_performance_source_dropped)
    row.typography_double_clicked.connect(self._open_typography_editor)
    row.typography_context_menu.connect(self._show_typography_menu)
    row.typography_changed.connect(self._on_typography_changed)
    row.typography_actor_selected.connect(self._on_typography_actor_selected)
    row.zoom_double_clicked.connect(self._open_zoom_editor)
    row.zoom_context_menu.connect(self._show_zoom_menu)
    row.zoom_changed.connect(self._on_track_zoom_changed)
    row.editor_preset_dropped.connect(self._on_workflow_preset_dropped)
    row.clip_drag_delta.connect(self._on_clip_drag_delta)
    row.cross_track_group_drag_delta.connect(self._on_cross_track_group_drag_delta)
    row.set_clip_drag_validator(self._validate_clip_drag_delta)
    # Seed the row with current snap targets so it immediately picks
    # up playhead + marker positions without waiting for the next move.
    row.set_extra_snap_targets(
        [self._player.position()] + [int(m["ms"]) for m in self._timeline_markers]
    )
    row.set_edit_tool_mode(getattr(self, "_timeline_tool_mode", "select"))
    row.set_focused_clip_role(str(getattr(self, "_nle_role_lane_focus", "") or ""))
    self._track_rows[track.id] = row
    # Insert video track BEFORE any audio track rows so video always
    # sits above audio in the timeline (DaVinci / Premiere convention).
    insert_idx = self._tracks_layout.count() - 1  # default: before stretch
    for i in range(self._tracks_layout.count()):
        item = self._tracks_layout.itemAt(i)
        if item and item.widget() and item.widget() in self._audio_rows.values():
            insert_idx = i
            break
    self._tracks_layout.insertWidget(insert_idx, row)
    # Belt-and-suspenders: re-assert the fixed height + visible
    # state AND force a layout activation. Qt's ``insertWidget``
    # queues the geometry update for the next event loop spin ??
    # if any code reads ``row.size()`` before that spin lands it
    # sees the default 640??80, which can also leave the row
    # invisible until a downstream paint kicks layout. Calling
    # ``invalidate`` + ``activate`` resolves the geometry
    # synchronously so subsequent reads + paints are correct.
    row.setFixedHeight(
        row.LABEL_H + row.TIMELINE_H + TRACK_V_PADDING,
    )
    row.show()
    self._tracks_layout.invalidate()
    self._tracks_layout.activate()
    self._tracks_host.adjustSize()
    self._refresh_video_row_lane_indices()
    self._update_tracks_host_width()


def _refresh_video_row_lane_indices(self) -> None:
    video_index = 0
    performance_index = 0
    rows = getattr(self, "_track_rows", {}) or {}
    for track in getattr(self, "_tracks", []) or []:
        row = rows.get(getattr(track, "id", None))
        if row is None or not hasattr(row, "set_lane_index"):
            continue
        is_performance = False
        detector = getattr(row, "_is_performance_source_track", None)
        if callable(detector):
            try:
                is_performance = bool(detector())
            except Exception:
                is_performance = False
        if is_performance:
            performance_index += 1
            row.set_lane_index(performance_index)
        else:
            video_index += 1
            row.set_lane_index(video_index)
    refresh_roles = getattr(self, "_refresh_nle_role_filter_bar", None)
    if callable(refresh_roles):
        refresh_roles()
    anchor_overlay = getattr(self, "_connected_anchor_overlay", None)
    refresh_anchor_overlay = getattr(anchor_overlay, "refresh", None)
    if callable(refresh_anchor_overlay):
        refresh_anchor_overlay()


def _add_audio_track_with_source(self, path: Path, *, open_editor: bool = False) -> None:
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
    self._try_apply_startup_template_if_ready("audio import")
    if open_editor:
        # Defer the editor open one event-loop tick so the row
        # widget + audio mixer are fully wired before we hand the
        # clip off to SoundEditorWindow (which immediately queries
        # the parent for the owning track to seed volume / pan).
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, lambda t=tid, c=clip.id: self._open_sound_editor(t, c))


def _start_waveform_extraction(self, clip: AudioClip) -> None:
    if clip.source_path is None:
        return
    cached = get_cached_waveform(clip.source_path)
    if cached is not None:
        clip.waveform = cached
        self._refresh_waveform_target_ui(clip)
        from PySide6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, lambda _c=clip: self._start_spectrum_extraction(_c))
        return

    key = audio_file_cache_key(clip.source_path)
    self._remove_clip_from_waveform_jobs(clip)
    existing_jid = self._waveform_source_jobs.get(key)
    if existing_jid is not None and existing_jid in self._waveform_extractors:
        waiters = self._waveform_clip_map.setdefault(existing_jid, [])
        if not any(c is clip for c in waiters):
            waiters.append(clip)
        return
    # Use a small sequential job counter as the extractor key ??
    # avoids id() overflow and clip.id collisions across sessions.
    if not hasattr(self, "_waveform_job_seq"):
        self._waveform_job_seq: int = 1
    if not hasattr(self, "_waveform_clip_map"):
        self._waveform_clip_map: dict[int, "AudioClip"] = {}
    # Cancel any existing job for the same clip object.
    old_jid = next((jid for jid, c in self._waveform_clip_map.items() if c is clip), None)
    if old_jid is not None:
        prev = self._waveform_extractors.pop(old_jid, None)
        self._waveform_clip_map.pop(old_jid, None)
        if prev is not None:
            try:
                prev.ready.disconnect()
                prev.failed.disconnect()
            except Exception:
                pass
    jid = self._waveform_job_seq
    self._waveform_job_seq += 1
    self._waveform_clip_map[jid] = [clip]
    self._waveform_job_key[jid] = key
    self._waveform_source_jobs[key] = jid
    ex = WaveformExtractor(jid, clip.source_path)
    ex.ready.connect(self._on_waveform_ready)
    ex.failed.connect(self._on_waveform_failed)
    ex.finished.connect(ex.deleteLater)
    self._waveform_extractors[jid] = ex
    ex.start()
    # Start spectrum extraction after waveform (500ms delay to avoid contention).
    from PySide6.QtCore import QTimer as _QTimer
    _QTimer.singleShot(600, lambda _c=clip: self._start_spectrum_extraction(_c))


def _remove_clip_from_waveform_jobs(self, clip: AudioClip) -> None:
    for jid, waiters in list(getattr(self, "_waveform_clip_map", {}).items()):
        kept = [c for c in waiters if c is not clip]
        if len(kept) == len(waiters):
            continue
        if kept:
            self._waveform_clip_map[jid] = kept
            continue
        self._cancel_waveform_job(jid)


def _cancel_waveform_job(self, jid: int) -> None:
    key = getattr(self, "_waveform_job_key", {}).pop(jid, None)
    if key is not None:
        getattr(self, "_waveform_source_jobs", {}).pop(key, None)
    getattr(self, "_waveform_clip_map", {}).pop(jid, None)
    ex = getattr(self, "_waveform_extractors", {}).pop(jid, None)
    if ex is not None:
        try:
            ex.ready.disconnect()
            ex.failed.disconnect()
        except Exception:
            pass
        try:
            ex.quit()
        except Exception:
            pass


def _refresh_waveform_target_ui(self, target: AudioClip) -> None:
    for track in self._audio_tracks:
        if any(c is target for c in track.clips):
            row = self._audio_rows.get(track.id)
            if row is not None:
                row.clear_waveform_error(target.id)
                row.update()
            break
    for editor in getattr(self, "_sound_editors", []):
        editor_clip = getattr(editor, "clip", None)
        if editor_clip is None and hasattr(editor, "current_clip"):
            try:
                editor_clip = editor.current_clip()
            except Exception:
                editor_clip = None
        if editor_clip is target and hasattr(editor, "refresh_waveform"):
            editor.refresh_waveform()
    panel = getattr(self, "_workbench_panel", None)
    if panel is not None and hasattr(panel, "current_target"):
        try:
            current = panel.current_target()
        except Exception:
            current = None
        if current is not None:
            current_clip = current[2] if current[0] == "audio" and len(current) > 2 else current[1] if current[0] == "audio_source" and len(current) > 1 else None
            if current_clip is target and hasattr(panel, "refresh_sound_editor_waveform"):
                panel.refresh_sound_editor_waveform()


def _start_spectrum_extraction(self, clip: AudioClip) -> None:
    if clip.source_path is None:
        return
    cached = get_cached_spectrum(clip.source_path)
    if cached is not None:
        clip.spectrum_bins = cached
        for track in self._audio_tracks:
            if any(c is clip for c in track.clips):
                row = self._audio_rows.get(track.id)
                if row is not None:
                    row.update()
                break
        return
    if not hasattr(self, "_spectrum_map"):
        self._spectrum_map: dict = {}   # sp_ex -> clip (keeps sp_ex alive)
    key = audio_file_cache_key(clip.source_path)
    existing = self._spectrum_source_jobs.get(key)
    if existing is not None and existing.isRunning():
        waiters = self._spectrum_map.setdefault(existing, [])
        if not any(c is clip for c in waiters):
            waiters.append(clip)
        return
    sp_ex = SpectrumExtractor(clip.source_path)
    # Store sp_ex as key to prevent GC while thread is running.
    self._spectrum_map[sp_ex] = [clip]
    self._spectrum_source_jobs[key] = sp_ex
    sp_ex.ready.connect(self._on_spectrum_ready)
    sp_ex.finished.connect(sp_ex.deleteLater)
    sp_ex.finished.connect(
        lambda _ex=sp_ex, _key=key: (
            self._spectrum_map.pop(_ex, None),
            self._spectrum_source_jobs.pop(_key, None),
        )
    )
    sp_ex.start()


def _on_spectrum_ready(self, bins) -> None:
    """Called on the main thread via Qt auto-queued cross-thread connection."""
    sp_map = getattr(self, "_spectrum_map", {})
    sender = self.sender()
    # sender is the SpectrumExtractor; look it up directly in map.
    targets = sp_map.get(sender) if sender else None
    if isinstance(targets, AudioClip):
        targets = [targets]
    if not targets or bins is None:
        return
    if targets[0].source_path is not None:
        store_cached_spectrum(targets[0].source_path, bins)
    for target in targets:
        target.spectrum_bins = get_cached_spectrum(target.source_path) if target.source_path else bins
        if target.spectrum_bins is None:
            target.spectrum_bins = bins
        for track in self._audio_tracks:
            if any(c is target for c in track.clips):
                row = self._audio_rows.get(track.id)
                if row is not None:
                    row.update()
                break


def _on_waveform_ready(self, oid: int, peaks) -> None:
    import sys
    _mx = float(peaks.max()) if hasattr(peaks, 'max') else 0
    _sh = getattr(peaks, 'shape', '?')
    msg = f"[waveform] ready  oid={oid} shape={_sh} max={_mx:.4f}\n"
    print(msg, end='', file=sys.stderr, flush=True)
    try:
        from app.paths import runtime_log_dir

        with open(runtime_log_dir() / "waveform_debug.log", "a", encoding="utf-8") as _f:
            import datetime as _dt
            _f.write(f"{_dt.datetime.now().isoformat()} {msg}")
    except Exception:
        pass
    clip_map = getattr(self, "_waveform_clip_map", {})
    targets = clip_map.pop(oid, None) or []
    if isinstance(targets, AudioClip):
        targets = [targets]
    key = getattr(self, "_waveform_job_key", {}).pop(oid, None)
    if key is not None:
        getattr(self, "_waveform_source_jobs", {}).pop(key, None)
    self._waveform_extractors.pop(oid, None)
    if not targets:
        return
    if targets[0].source_path is not None:
        store_cached_waveform(targets[0].source_path, peaks)
    for target in targets:
        target.waveform = get_cached_waveform(target.source_path) if target.source_path else peaks
        if target.waveform is None:
            target.waveform = peaks
        self._refresh_waveform_target_ui(target)


def _on_waveform_failed(self, oid: int, reason: str) -> None:
    import sys
    msg = f"[waveform] FAILED oid={oid} reason={reason[:120]}\n"
    print(msg, end='', file=sys.stderr, flush=True)
    try:
        from app.paths import runtime_log_dir

        with open(runtime_log_dir() / "waveform_debug.log", "a", encoding="utf-8") as _f:
            import datetime as _dt
            _f.write(f"{_dt.datetime.now().isoformat()} {msg}")
    except Exception:
        pass
    clip_map = getattr(self, "_waveform_clip_map", {})
    targets = clip_map.pop(oid, None) or []
    if isinstance(targets, AudioClip):
        targets = [targets]
    key = getattr(self, "_waveform_job_key", {}).pop(oid, None)
    if key is not None:
        getattr(self, "_waveform_source_jobs", {}).pop(key, None)
    self._waveform_extractors.pop(oid, None)
    if not targets:
        return
    for target in targets:
        for track in self._audio_tracks:
            if any(c is target for c in track.clips):
                row = self._audio_rows.get(track.id)
                if row is not None:
                    row.set_waveform_error(target.id, reason)
                break


def _populate_video_track(self, track_id: int, path: Path) -> None:
    track = self._find_track(track_id)
    if track is None or track.source_path is not None:
        return
    track.source_path = path
    track.hdr_info = _probe_track_hdr_info(path)
    row = self._track_rows.get(track_id)
    if row is not None:
        row.update()
    self._start_thumbnail_extraction(track)
    self._refresh_player_tracks(render_immediately=False)
    _ensure_video_clips(track)
    auto_polish_added = 0
    for clip in getattr(track, "clips", []) or []:
        auto_polish_added += self._maybe_apply_default_screenstudio_polish_to_clip(
            track,
            clip,
            reason="track populate",
        )
    # Repaint AFTER ``_ensure_video_clips`` populates the stored
    # clips list ??without this the "empty slot" paint sticks.
    # ``update()`` only; an extra ``_recalc_width`` here destabilised
    # the layout reflow on some Qt builds.
    if row is not None:
        row.update()
    self._refresh_player_tracks(render_immediately=False)
    self._refresh_visual_preview_after_timeline_change()
    if track_id == self._active_track_id:
        self._refresh_workbench()
    if auto_polish_added > 0:
        self._flash_status(f"Screen Studio polish applied: {auto_polish_added} zoom window(s)")
    self._try_apply_startup_template_if_ready("video import")


def _insert_audio_track_widget(self, track: AudioTrack) -> None:
    row = AudioTrackRow(track)
    row.installEventFilter(self)
    row.set_px_per_sec(self._px_per_sec)
    row.clicked.connect(self._set_active_track)
    row.position_requested.connect(self._on_track_position_requested)
    row.volume_changed.connect(self._on_audio_volume_changed)
    row.row_context_menu.connect(self._on_audio_row_context_menu)
    row.clip_context_menu.connect(self._on_audio_clip_context_menu)
    row.load_source_requested.connect(self._on_audio_load_source_requested)
    row.media_dropped.connect(self._on_media_dropped_on_audio_row)
    row.track_changed.connect(self._on_audio_track_changed)
    row.clip_selection_changed.connect(self._on_audio_clip_selection_changed)
    row.open_editor_requested.connect(self._open_sound_editor)
    self._audio_rows[track.id] = row
    self._refresh_audio_row_lane_indices()
    self._tracks_layout.insertWidget(self._tracks_layout.count() - 1, row)
    self._update_tracks_host_width()
    # Rebuild mixer panel if it's visible
    if hasattr(self, "_audio_mixer_panel") and self._audio_mixer_panel.isVisible():
        self._audio_mixer_panel.rebuild(self._audio_tracks)


def _refresh_audio_row_lane_indices(self) -> None:
    for index, track in enumerate(getattr(self, "_audio_tracks", []) or [], start=1):
        row = getattr(self, "_audio_rows", {}).get(getattr(track, "id", None))
        if row is not None and hasattr(row, "set_lane_index"):
            row.set_lane_index(index)


def _append_clip_to_track(self, track: "VideoTrack", path: Path) -> None:
    """Industry-standard multi-source append: add a new clip at the tail
    of an existing video track without creating a new track row.

    - Probes ``path`` duration with cv2 (fast, no new QThread needed).
    - Creates a ``VideoClip`` with its own ``source_path`` and places it
      immediately after the current rightmost clip.
    - Starts per-clip thumbnail extraction so thumbnails are kept separate
      from the existing track-level thumbnails.
    - Calls ``_refresh_player_tracks`` so the player opens a decoder for
      the new source and recomputes project duration.
    """
    from app.image_media import is_image_path
    if is_image_path(path):
        from app.video_editor_media_import_controller import append_image_clip_to_track

        append_image_clip_to_track(self, track, path)
        return
    from app.timeline_model import VideoClip as _VC, NodeGraph as _NG
    duration_ms = probe_video_duration_ms(path)
    if duration_ms <= 0:
        QMessageBox.warning(
            self,
            tr("veditor.title"),
            tr("veditor.audio.error.undecodable", path=str(path)),
        )
        return
    tail_ms = max(
        (int(c.timeline_out_ms) for c in track.clips), default=0
    )
    clip_id_val = getattr(self, "_next_video_clip_id", 2_000_000)
    self._next_video_clip_id = clip_id_val + 1
    new_clip = _VC(
        id=clip_id_val,
        source_path=path,
        source_duration_ms=duration_ms,
        timeline_in_ms=tail_ms,
        source_in_ms=0,
        source_out_ms=duration_ms,
        node_graph=_NG.default(),
    )
    track.clips.append(new_clip)
    auto_polish_added = self._maybe_apply_default_screenstudio_polish_to_clip(
        track,
        new_clip,
        reason="clip append",
    )
    # Update track-level display_name to reflect multiple sources.
    # (VideoTrack.display_name property already handles this.)
    self._start_thumbnail_extraction_for_clip(new_clip, track.id)
    self._refresh_player_tracks(render_immediately=False)
    self._refresh_visual_preview_after_timeline_change()
    row = self._track_rows.get(track.id)
    if row is not None:
        row.flash_timeline_burst("cut", int(tail_ms))
        row.update()
    self._register_change("append clip")
    if auto_polish_added > 0:
        self._flash_status(f"Screen Studio polish applied: {auto_polish_added} zoom window(s)")
    self._try_apply_startup_template_if_ready("video import")


def _extract_audio_from_video(self, track: VideoTrack) -> None:
    """Create a new AudioTrack whose single clip points at the video
    file itself. FFmpeg / QMediaPlayer both treat a video file as a
    valid audio source ??they decode the audio stream and ignore
    the video stream ??so this is effectively "ripping the BGM" as
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
