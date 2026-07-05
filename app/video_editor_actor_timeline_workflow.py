from __future__ import annotations

from app.live2d.actor_track import Live2DActorTrack
from app.spine_editor.actor_track import SpineActorTrack
from app.timeline_ruler import TimelineRuler
from app.video_editor_actor_workspaces import (
    open_live2d_clip_editor as _open_live2d_clip_editor_ui,
    open_spine_clip_editor as _open_spine_clip_editor_ui,
    rebuild_live2d_actor_lanes as _rebuild_live2d_actor_lanes_ui,
    rebuild_spine_actor_lanes as _rebuild_spine_actor_lanes_ui,
)


def _open_live2d_viewer(self) -> None:
    from app.live2d.live2d_viewer import Live2DEditorWindow

    if not hasattr(self, "_live2d_editor") or self._live2d_editor is None:
        self._live2d_editor = Live2DEditorWindow(self)
        self._live2d_editor.destroyed.connect(lambda: setattr(self, "_live2d_editor", None))
    self._live2d_editor.show()
    self._live2d_editor.raise_()
    self._live2d_editor.activateWindow()


def _open_spine_editor(self) -> None:
    from app.spine_editor.editor_window import SpineEditorWindow

    if not getattr(self, "_spine_editor", None):
        self._spine_editor = SpineEditorWindow(self)
        self._spine_editor.destroyed.connect(lambda: setattr(self, "_spine_editor", None))
    self._spine_editor.show()
    self._spine_editor.raise_()
    self._spine_editor.activateWindow()


def _focus_actor_clip_for_edit(self, clip, *, refresh: bool = True) -> None:
    if clip is None or not hasattr(self, "_player"):
        return
    start_guard = getattr(self, "_start_preview_transition_guard", None)
    backup = start_guard(900) if callable(start_guard) else None
    try:
        start = int(getattr(clip, "start_ms", 0) or 0)
        end = int(getattr(clip, "end_ms", start) or start)
        if end <= start:
            end = start + int(getattr(clip, "duration_ms", 0) or 0)
        if end <= start:
            return
        current = int(self._player.position())
        target = current
        if current < start or current >= end:
            target = min(end - 1, start + max(1, min(120, (end - start) // 8)))
        if target != current:
            self._player.set_position(target)
            ensure_visible = getattr(self, "_ensure_playhead_visible", None)
            if callable(ensure_visible):
                ensure_visible()
        elif refresh:
            self._player.refresh_current_frame()
    except Exception:
        try:
            if refresh:
                self._player.refresh_current_frame()
        except Exception:
            pass
    restore_guard = getattr(self, "_schedule_preview_transition_restore", None)
    if callable(restore_guard):
        restore_guard(backup)


def _on_spine_clip_dclick(self, clip) -> None:
    _open_spine_clip_editor_ui(self, clip)


def _on_live2d_clip_dclick(self, clip) -> None:
    _open_live2d_clip_editor_ui(self, clip)


def _add_live2d_actor_at_playhead(self) -> None:
    if not self._live2d_actor_tracks:
        self._add_live2d_actor_track()
    start_ms = getattr(self._player, "_position_ms", 0)
    self._live2d_lane_rows[0]._create_clip("", start_ms)
    new_clip = self._live2d_actor_tracks[0].clips[-1]
    self._on_live2d_clip_dclick(new_clip)


def _add_live2d_actor_track(self) -> Live2DActorTrack:
    tid = self._next_live2d_id
    self._next_live2d_id += 1
    track = Live2DActorTrack(id=tid, label=f"Live2D {tid}")
    self._live2d_actor_tracks.append(track)
    self._insert_live2d_actor_lane(track)
    self._player.set_live2d_actor_tracks(self._live2d_actor_tracks)
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    return track


def _timeline_content_margin(self) -> int:
    return int(getattr(TimelineRuler, "MARGIN", 10))


def _tracks_host_drop_model(self, path: str, drop_x: float) -> None:
    margin = self._timeline_content_margin()
    start_ms = max(0, int((drop_x - margin) / max(1.0, self._px_per_sec) * 1000))
    self._record_editor_action(
        "timeline.drop_live2d",
        path=path,
        drop_x=drop_x,
        start_ms=start_ms,
    )
    if not self._live2d_actor_tracks:
        self._add_live2d_actor_track()
    self._live2d_lane_rows[0]._create_clip(path, start_ms)


def _rebuild_spine_actor_lanes(self) -> None:
    _rebuild_spine_actor_lanes_ui(self)
    self._player.set_spine_actor_tracks(self._spine_actor_tracks)
    self._refresh_player_tracks()
    self._update_tracks_host_width()


def _add_spine_actor_track(self) -> SpineActorTrack:
    tid = self._next_actor_id
    self._next_actor_id += 1
    track = SpineActorTrack(id=tid, label=f"Spine {tid}")
    self._spine_actor_tracks.append(track)
    self._insert_spine_actor_lane(track)
    self._player.set_spine_actor_tracks(self._spine_actor_tracks)
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    return track


def _on_actor_clip_changed(self) -> None:
    self._player.set_spine_actor_tracks(self._spine_actor_tracks)
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    if hasattr(self, "_player"):
        self._player.refresh_current_frame()


def _add_spine_actor_at_playhead(self) -> None:
    if not self._spine_actor_tracks:
        self._add_spine_actor_track()
    start_ms = getattr(self._player, "_position_ms", 0)
    self._actor_lane_rows[0]._create_clip("", start_ms)
    new_clip = self._spine_actor_tracks[0].clips[-1]
    self._on_spine_clip_dclick(new_clip)


def _tracks_host_drop_spine(self, path: str, drop_x: float) -> None:
    margin = self._timeline_content_margin()
    start_ms = max(0, int((drop_x - margin) / max(1.0, self._px_per_sec) * 1000))
    self._record_editor_action(
        "timeline.drop_spine",
        path=path,
        drop_x=drop_x,
        start_ms=start_ms,
    )
    if not self._spine_actor_tracks:
        self._add_spine_actor_track()
    self._actor_lane_rows[0]._create_clip(path, start_ms)


def _rebuild_live2d_actor_lanes(self) -> None:
    _rebuild_live2d_actor_lanes_ui(self)
    self._player.set_live2d_actor_tracks(self._live2d_actor_tracks)
    self._refresh_player_tracks()
    self._update_tracks_host_width()


def _on_live2d_clip_changed(self) -> None:
    self._player.set_live2d_actor_tracks(self._live2d_actor_tracks)
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    self._refresh_live2d_workbench_selection()
    studio = getattr(self, "_vtuber_studio_window", None)
    if studio is not None and studio.isVisible():
        studio.update_from_editor(self)


def _export_track_zoom_actors_only(track) -> list:
    actors = list(getattr(track, "zoom_actors", []) or [])
    actors.sort(key=lambda z: int(getattr(z, "start_ms", 0) or 0))
    return actors


def _has_live2d_actor_clips(self) -> bool:
    return any(
        bool(getattr(track, "clips", []) or [])
        for track in getattr(self, "_live2d_actor_tracks", []) or []
    )


def _live2d_actor_extent_ms(self) -> int:
    return max(
        (
            int(getattr(clip, "end_ms", 0) or 0)
            for track in getattr(self, "_live2d_actor_tracks", []) or []
            for clip in getattr(track, "clips", []) or []
        ),
        default=0,
    )


def _apply_performance_source_to_selected_avatar(self) -> None:
    clip = self._selected_live2d_clip_for_mapping()
    if clip is not None:
        self._apply_performance_source_to_selected_live2d()
        return
    bridge = {}
    settings = getattr(self, "_project_settings", {}) or {}
    if isinstance(settings, dict):
        bridge = settings.get("vseeface_bridge") if isinstance(settings.get("vseeface_bridge"), dict) else {}
    avatar_vrm = str((bridge or {}).get("avatar_vrm") or (bridge or {}).get("vrm") or "").strip()
    if avatar_vrm:
        self._flash_status(
            "VRM/VSeeFace targets use the VTuber bridge pose stream; "
            "direct key baking is Live2D-only for now"
        )
    else:
        self._flash_status("Select or configure a VRM/VSeeFace or Live2D avatar target first")
