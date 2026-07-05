from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from app.audio_tracks import is_video_path
from app.i18n import tr
from app.media_asset_routing import (
    performance_source_paths_from_mime as _shared_performance_source_paths_from_mime,
    timeline_media_paths_from_mime as _shared_timeline_media_paths_from_mime,
)
from app.video_editor_thumbnailing import probe_video_duration_ms
from app.video_track_legacy import VideoTrack


def _use_vrm_media_as_avatar_target(self, path: str) -> None:
    avatar = Path(path).expanduser()
    if avatar.suffix.lower() != ".vrm":
        self._flash_status("Select a .vrm avatar file")
        return
    settings = dict(getattr(self, "_project_settings", {}) or {})
    bridge = dict(settings.get("vseeface_bridge") if isinstance(settings.get("vseeface_bridge"), dict) else {})
    studio = dict(settings.get("vtuber_studio") if isinstance(settings.get("vtuber_studio"), dict) else {})
    bridge["avatar_vrm"] = str(avatar)
    studio["avatar_target_id"] = "vrm:vseeface_bridge"
    settings["vseeface_bridge"] = bridge
    settings["vtuber_studio"] = studio
    self._project_settings = settings
    player = getattr(self, "_player", None)
    if player is not None and hasattr(player, "set_project_settings"):
        player.set_project_settings(settings)
    self._register_change("Select VRM avatar target")
    self._flash_status(f"VRM Avatar Target selected: {avatar.name}")
    studio_window = getattr(self, "_vtuber_studio_window", None)
    if studio_window is not None and studio_window.isVisible():
        studio_window.update_from_editor(self)
    recorder = getattr(self, "_record_editor_action", None)
    if callable(recorder):
        recorder(
            "vtuber.avatar_target.select_vrm_media",
            path=str(avatar),
            target_id="vrm:vseeface_bridge",
        )


def _media_pool_marks_performance_source(self, path: Path | str) -> bool:
    pool = getattr(self, "_media_pool", None)
    checker = getattr(pool, "is_performance_source_path", None)
    if callable(checker):
        try:
            return bool(checker(path))
        except Exception:
            return False
    return False


def _mark_vtuber_performance_source(obj):
    try:
        from app.vtuber.performance_source import (
            PERFORMANCE_SOURCE_LABEL,
            mark_performance_source_object,
        )

        mark_performance_source_object(obj)
        if hasattr(obj, "label") and not str(getattr(obj, "label", "") or ""):
            setattr(obj, "label", PERFORMANCE_SOURCE_LABEL)
    except Exception:
        try:
            setattr(obj, "performance_source", True)
            setattr(obj, "vtuber_performance_source", True)
            setattr(obj, "track_type", "vtuber_performance_source")
            setattr(obj, "program_output", False)
        except Exception:
            pass
    return obj


def _performance_source_paths_from_mime(self, mime: QMimeData) -> list[Path]:
    return _shared_performance_source_paths_from_mime(
        mime,
        self._media_pool_marks_performance_source,
    )


def _timeline_media_paths_from_mime(self, mime: QMimeData) -> list[Path]:
    return _shared_timeline_media_paths_from_mime(mime)


def _ensure_performance_source_track(self) -> "VideoTrack":
    try:
        from app.vtuber.performance_source import is_performance_source_track
    except Exception:
        is_performance_source_track = lambda track: bool(getattr(track, "performance_source", False))
    for track in getattr(self, "_tracks", []) or []:
        if is_performance_source_track(track):
            return track
    tid = self._next_track_id
    self._next_track_id += 1
    track = VideoTrack(id=tid)
    self._mark_vtuber_performance_source(track)
    track.source_path = None
    track.clips = []
    track.clips_explicit = True
    self._tracks.append(track)
    self._insert_track_widget(track)
    return track


def _add_performance_source_clip(self, path: Path, start_ms: int | None = None) -> None:
    if not is_video_path(path):
        return
    if hasattr(self, "_media_pool"):
        self._media_pool.add_path(path)
        setter = getattr(self._media_pool, "set_performance_source_path", None)
        if callable(setter):
            try:
                setter(path, True)
            except Exception:
                pass
    duration_ms = probe_video_duration_ms(path)
    if duration_ms <= 0:
        QMessageBox.warning(
            self,
            tr("veditor.title"),
            tr("veditor.audio.error.undecodable", path=str(path)),
        )
        return
    if start_ms is None:
        start_ms = int(getattr(self._player, "position", lambda: 0)())
    track = self._ensure_performance_source_track()
    from app.timeline_model import NodeGraph as _NG, VideoClip as _VC

    clip_id_val = getattr(self, "_next_video_clip_id", 2_000_000)
    self._next_video_clip_id = clip_id_val + 1
    clip = _VC(
        id=clip_id_val,
        source_path=path,
        source_duration_ms=duration_ms,
        timeline_in_ms=max(0, int(start_ms or 0)),
        source_in_ms=0,
        source_out_ms=duration_ms,
        node_graph=_NG.default(),
    )
    self._mark_vtuber_performance_source(clip)
    track.clips.append(clip)
    track.clips.sort(key=lambda c: int(getattr(c, "timeline_in_ms", 0) or 0))
    track.clips_explicit = True
    self._start_thumbnail_extraction_for_clip(clip, track.id)
    self._set_active_track(track.id)
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    row = self._track_rows.get(track.id)
    if row is not None:
        row.flash_timeline_burst("drop", int(getattr(clip, "timeline_in_ms", 0) or 0))
        row.update()
    self._register_change("add performance source")
    self._record_editor_action(
        "vtuber.performance_source.add",
        path=str(path),
        start_ms=int(getattr(clip, "timeline_in_ms", 0) or 0),
        duration_ms=int(duration_ms),
    )
    self._flash_status(f"Performance Source added: {path.name}")


def _on_performance_source_dropped(self, path: Path, project_ms: int) -> None:
    self._add_performance_source_clip(Path(path), int(project_ms))


def _on_ar_pbr_asset_dropped_on_video_row(self, path: Path, project_ms: int) -> None:
    self._add_ar_pbr_asset_to_preview(
        Path(path),
        image_point=(0.5, 0.62),
        start_ms=max(0, int(project_ms)),
    )

