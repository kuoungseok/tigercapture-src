"""Duck-typed media import/drop controller helpers for VideoEditorWindow.

This module keeps route decisions separate from the large Qt window class.
It deliberately talks to an ``owner`` through private-method duck typing so
VideoEditorWindow can adopt these helpers as thin wrappers without forcing a
class dependency back into this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from app.audio_tracks import (
    AudioClip,
    AudioTrack,
    is_audio_path,
    is_video_path,
    probe_audio_duration_ms,
)
from app.image_media import DEFAULT_IMAGE_DURATION_MS, is_image_path
from app.media_asset_routing import (
    ar_pbr_paths_from_mime as _shared_ar_pbr_paths_from_mime,
    mmd_paths_from_mime as _shared_mmd_paths_from_mime,
    motion_project_paths_from_mime as _shared_motion_project_paths_from_mime,
    performance_source_paths_from_mime as _shared_performance_source_paths_from_mime,
    timeline_media_paths_from_mime as _shared_timeline_media_paths_from_mime,
    vrm_avatar_paths_from_mime as _shared_vrm_avatar_paths_from_mime,
)
from app.timeline_model import NodeGraph, VideoClip
from app.video_editor_thumbnailing import probe_video_duration_ms
from app.video_track_legacy import VideoTrack, _ensure_video_clips


ROUTE_NONE = "none"
ROUTE_VRM_AVATAR = "vrm_avatar"
ROUTE_MMD = "mmd"
ROUTE_MOTION = "motion_actor"
ROUTE_AR_PBR = "ar_pbr"
ROUTE_PERFORMANCE_SOURCE = "performance_source"
ROUTE_VIDEO = "video"
ROUTE_IMAGE = "image"
ROUTE_AUDIO = "audio"

TARGET_TIMELINE = "timeline"
TARGET_WINDOW = "window"
TARGET_TRACKS_HOST = "tracks_host"
TARGET_PREVIEW = "preview"
TARGET_VIDEO_ROW = "video_row"
TARGET_AUDIO_ROW = "audio_row"

_WINDOW_PRIORITY = (
    ROUTE_VRM_AVATAR,
    ROUTE_MMD,
    ROUTE_MOTION,
    ROUTE_PERFORMANCE_SOURCE,
    ROUTE_AR_PBR,
    ROUTE_VIDEO,
    ROUTE_IMAGE,
    ROUTE_AUDIO,
)
_TRACKS_HOST_PRIORITY = (
    ROUTE_MMD,
    ROUTE_MOTION,
    ROUTE_PERFORMANCE_SOURCE,
    ROUTE_AR_PBR,
    ROUTE_VIDEO,
    ROUTE_IMAGE,
    ROUTE_AUDIO,
)
_PREVIEW_PRIORITY = (
    ROUTE_VRM_AVATAR,
    ROUTE_MMD,
    ROUTE_MOTION,
    ROUTE_AR_PBR,
)
_VIDEO_ROW_PRIORITY = (
    ROUTE_MMD,
    ROUTE_MOTION,
    ROUTE_AR_PBR,
    ROUTE_PERFORMANCE_SOURCE,
    ROUTE_VIDEO,
    ROUTE_IMAGE,
    ROUTE_AUDIO,
)
_AUDIO_ROW_PRIORITY = (
    ROUTE_MMD,
    ROUTE_MOTION,
    ROUTE_AR_PBR,
    ROUTE_PERFORMANCE_SOURCE,
    ROUTE_VIDEO,
    ROUTE_IMAGE,
    ROUTE_AUDIO,
)


@dataclass(frozen=True)
class MediaImportDecision:
    """A pure description of what a mime/path import should do."""

    route: str = ROUTE_NONE
    paths: tuple[Path, ...] = ()
    target: str = TARGET_TIMELINE
    track_id: int | None = None
    start_ms: int | None = None
    image_point: tuple[float, float] | None = None
    open_audio_editor: bool = False

    @property
    def handled(self) -> bool:
        return self.route != ROUTE_NONE and bool(self.paths)

    @property
    def path(self) -> Path | None:
        return self.paths[0] if self.paths else None


def _safe_call(func: Callable[..., Any] | None, *args: Any, **kwargs: Any) -> Any:
    if not callable(func):
        return None
    try:
        return func(*args, **kwargs)
    except TypeError:
        # Some existing owner helpers do not accept newer keyword arguments.
        if kwargs:
            try:
                return func(*args)
            except Exception:
                return None
        return None
    except Exception:
        return None


def _as_paths(value: Iterable[Any] | Any) -> tuple[Path, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, Path)):
        value = [value]
    paths: list[Path] = []
    for item in value:
        try:
            path = Path(item)
        except Exception:
            continue
        if str(path):
            paths.append(path)
    return tuple(paths)


def _owner_paths(
    owner: Any,
    helper_name: str,
    fallback: Callable[..., list[Path]],
    mime: Any,
    *fallback_args: Any,
) -> tuple[Path, ...]:
    helper = getattr(owner, helper_name, None)
    if callable(helper):
        return _as_paths(_safe_call(helper, mime))
    return _as_paths(fallback(mime, *fallback_args))


def vrm_avatar_paths_from_mime(owner: Any, mime: Any) -> tuple[Path, ...]:
    return _owner_paths(owner, "_vrm_avatar_paths_from_mime", _shared_vrm_avatar_paths_from_mime, mime)


def mmd_paths_from_mime(owner: Any, mime: Any) -> tuple[Path, ...]:
    return _owner_paths(owner, "_mmd_paths_from_mime", _shared_mmd_paths_from_mime, mime)


def motion_project_paths_from_mime(owner: Any, mime: Any) -> tuple[Path, ...]:
    return _owner_paths(
        owner,
        "_motion_project_paths_from_mime",
        _shared_motion_project_paths_from_mime,
        mime,
    )


def ar_pbr_paths_from_mime(owner: Any, mime: Any) -> tuple[Path, ...]:
    return _owner_paths(owner, "_ar_pbr_paths_from_mime", _shared_ar_pbr_paths_from_mime, mime)


def performance_source_paths_from_mime(owner: Any, mime: Any) -> tuple[Path, ...]:
    marker = getattr(owner, "_media_pool_marks_performance_source", None)
    return _owner_paths(
        owner,
        "_performance_source_paths_from_mime",
        _shared_performance_source_paths_from_mime,
        mime,
        marker if callable(marker) else None,
    )


def timeline_media_paths_from_mime(owner: Any, mime: Any) -> tuple[Path, ...]:
    return _owner_paths(owner, "_timeline_media_paths_from_mime", _shared_timeline_media_paths_from_mime, mime)


def route_mime_drop(
    owner: Any,
    mime: Any,
    *,
    target: str = TARGET_TIMELINE,
    track_id: int | None = None,
    start_ms: int | None = None,
    image_point: tuple[float, float] | None = None,
    open_audio_editor: bool = False,
) -> MediaImportDecision:
    """Classify a drop using the same special-before-media policy as the editor.

    The exact priority differs slightly by surface, matching the current
    window/row paths: tracks host routes performance-source before AR/PBR,
    while video rows keep AR/PBR before performance-source.
    """

    route_paths = {
        ROUTE_VRM_AVATAR: vrm_avatar_paths_from_mime(owner, mime),
        ROUTE_MMD: mmd_paths_from_mime(owner, mime),
        ROUTE_MOTION: motion_project_paths_from_mime(owner, mime),
        ROUTE_PERFORMANCE_SOURCE: performance_source_paths_from_mime(owner, mime),
        ROUTE_AR_PBR: ar_pbr_paths_from_mime(owner, mime),
    }
    media_paths = timeline_media_paths_from_mime(owner, mime)
    route_paths[ROUTE_VIDEO] = tuple(path for path in media_paths if is_video_path(path))
    route_paths[ROUTE_IMAGE] = tuple(path for path in media_paths if is_image_path(path))
    route_paths[ROUTE_AUDIO] = tuple(path for path in media_paths if is_audio_path(path))

    priorities = {
        TARGET_WINDOW: _WINDOW_PRIORITY,
        TARGET_TRACKS_HOST: _TRACKS_HOST_PRIORITY,
        TARGET_PREVIEW: _PREVIEW_PRIORITY,
        TARGET_VIDEO_ROW: _VIDEO_ROW_PRIORITY,
        TARGET_AUDIO_ROW: _AUDIO_ROW_PRIORITY,
        TARGET_TIMELINE: _WINDOW_PRIORITY,
    }.get(str(target or TARGET_TIMELINE), _WINDOW_PRIORITY)

    for route in priorities:
        paths = route_paths.get(route) or ()
        if paths:
            return MediaImportDecision(
                route=route,
                paths=paths,
                target=str(target or TARGET_TIMELINE),
                track_id=track_id,
                start_ms=start_ms,
                image_point=image_point,
                open_audio_editor=open_audio_editor,
            )
    return MediaImportDecision(
        route=ROUTE_NONE,
        target=str(target or TARGET_TIMELINE),
        track_id=track_id,
        start_ms=start_ms,
        image_point=image_point,
        open_audio_editor=open_audio_editor,
    )


def route_video_row_drop(owner: Any, track_id: int, mime: Any, *, start_ms: int | None = None) -> MediaImportDecision:
    return route_mime_drop(owner, mime, target=TARGET_VIDEO_ROW, track_id=int(track_id), start_ms=start_ms)


def route_audio_row_drop(owner: Any, track_id: int, mime: Any, *, start_ms: int | None = None) -> MediaImportDecision:
    return route_mime_drop(owner, mime, target=TARGET_AUDIO_ROW, track_id=int(track_id), start_ms=start_ms)


def route_tracks_host_drop(owner: Any, mime: Any, *, drop_x: float | None = None) -> MediaImportDecision:
    start_ms = timeline_start_ms_from_drop_x(owner, drop_x) if drop_x is not None else None
    return route_mime_drop(owner, mime, target=TARGET_TRACKS_HOST, start_ms=start_ms, image_point=(0.5, 0.62))


def route_preview_drop(
    owner: Any,
    mime: Any,
    *,
    image_point: tuple[float, float] | None = None,
) -> MediaImportDecision:
    return route_mime_drop(owner, mime, target=TARGET_PREVIEW, image_point=image_point)


def accepts_mime_drop(owner: Any, mime: Any, *, target: str = TARGET_TIMELINE) -> bool:
    return route_mime_drop(owner, mime, target=target).handled


def timeline_start_ms_from_drop_x(owner: Any, drop_x: float | int | None) -> int:
    margin_fn = getattr(owner, "_timeline_content_margin", None)
    margin = _safe_call(margin_fn)
    try:
        margin_value = float(margin if margin is not None else 0.0)
    except Exception:
        margin_value = 0.0
    try:
        px_per_sec = float(getattr(owner, "_px_per_sec", 1.0) or 1.0)
    except Exception:
        px_per_sec = 1.0
    try:
        x_value = float(drop_x if drop_x is not None else margin_value)
    except Exception:
        x_value = margin_value
    return max(0, int((x_value - margin_value) / max(1.0, px_per_sec) * 1000.0))


def _owner_track_list(owner: Any, attr: str) -> list[Any]:
    tracks = getattr(owner, attr, None)
    if not isinstance(tracks, list):
        tracks = []
        try:
            setattr(owner, attr, tracks)
        except Exception:
            pass
    return tracks


def _next_track_id(owner: Any) -> int:
    current = getattr(owner, "_next_track_id", None)
    try:
        tid = int(current)
    except Exception:
        used = [
            int(getattr(track, "id", 0) or 0)
            for track in list(getattr(owner, "_tracks", []) or []) + list(getattr(owner, "_audio_tracks", []) or [])
        ]
        tid = max(used, default=0) + 1
    try:
        setattr(owner, "_next_track_id", tid + 1)
    except Exception:
        pass
    return tid


def _next_video_clip_id(owner: Any) -> int:
    current = getattr(owner, "_next_video_clip_id", None)
    try:
        cid = int(current)
    except Exception:
        cid = 2_000_000
    try:
        setattr(owner, "_next_video_clip_id", cid + 1)
    except Exception:
        pass
    return cid


def _next_audio_clip_id(owner: Any) -> int:
    method = getattr(owner, "_next_clip_id", None)
    if callable(method):
        try:
            return int(method())
        except Exception:
            pass
    current = getattr(owner, "_next_audio_clip_id", None)
    try:
        cid = int(current)
    except Exception:
        cid = 1
    try:
        setattr(owner, "_next_audio_clip_id", cid + 1)
    except Exception:
        pass
    return cid


def _current_playhead_ms(owner: Any) -> int:
    player = getattr(owner, "_player", None)
    pos = getattr(player, "position", None)
    try:
        return max(0, int(pos() if callable(pos) else 0))
    except Exception:
        return 0


def _find_video_track(owner: Any, track_id: int | None) -> VideoTrack | Any | None:
    if track_id is None:
        return None
    finder = getattr(owner, "_find_track", None)
    found = _safe_call(finder, int(track_id))
    if found is not None:
        return found
    for track in getattr(owner, "_tracks", []) or []:
        try:
            if int(getattr(track, "id", -1)) == int(track_id):
                return track
        except Exception:
            continue
    return None


def _find_audio_track(owner: Any, track_id: int | None) -> AudioTrack | Any | None:
    if track_id is None:
        return None
    finder = getattr(owner, "_find_audio_track", None)
    found = _safe_call(finder, int(track_id))
    if found is not None:
        return found
    for track in getattr(owner, "_audio_tracks", []) or []:
        try:
            if int(getattr(track, "id", -1)) == int(track_id):
                return track
        except Exception:
            continue
    return None


def _register_in_media_pool(owner: Any, path: Path, *, performance_source: bool = False) -> None:
    pool = getattr(owner, "_media_pool", None)
    add_path = getattr(pool, "add_path", None)
    if callable(add_path):
        _safe_call(add_path, path)
    if performance_source:
        setter = getattr(pool, "set_performance_source_path", None)
        if callable(setter):
            _safe_call(setter, path, True)


def _refresh_after_timeline_change(owner: Any, *, render_immediately: bool | None = None) -> None:
    refresh = getattr(owner, "_refresh_player_tracks", None)
    if callable(refresh):
        if render_immediately is None:
            _safe_call(refresh)
        else:
            _safe_call(refresh, render_immediately=render_immediately)
    _safe_call(getattr(owner, "_refresh_visual_preview_after_timeline_change", None))
    _safe_call(getattr(owner, "_update_tracks_host_width", None))


def _row_for_track(owner: Any, track_id: int | None) -> Any | None:
    if track_id is None:
        return None
    rows = getattr(owner, "_track_rows", None)
    if isinstance(rows, dict):
        return rows.get(track_id)
    return None


def _row_for_audio_track(owner: Any, track_id: int | None) -> Any | None:
    if track_id is None:
        return None
    rows = getattr(owner, "_audio_rows", None)
    if isinstance(rows, dict):
        return rows.get(track_id)
    return None


def _flash_track_row(owner: Any, track_id: int | None, label: str, ms: int) -> None:
    row = _row_for_track(owner, track_id)
    if row is not None:
        _safe_call(getattr(row, "flash_timeline_burst", None), label, int(ms))
        _safe_call(getattr(row, "update", None))


def _touch_audio_track_ui(owner: Any, track: Any, clip: AudioClip | Any | None = None) -> None:
    row = _row_for_audio_track(owner, int(getattr(track, "id", 0) or 0))
    if row is not None:
        _safe_call(getattr(row, "refresh_from_track", None))
        _safe_call(getattr(row, "update", None))
    mixer = getattr(owner, "_audio_mixer", None)
    _safe_call(getattr(mixer, "update_track", None), track)
    if clip is not None:
        _safe_call(getattr(owner, "_start_waveform_extraction", None), clip)


def _mark_performance_source(obj: Any) -> Any:
    try:
        from app.vtuber.performance_source import mark_performance_source_object

        return mark_performance_source_object(obj)
    except Exception:
        for name, value in {
            "vtuber_performance_source": True,
            "performance_source": True,
            "is_performance_source": True,
            "track_type": "vtuber_performance_source",
            "program_output": False,
        }.items():
            try:
                setattr(obj, name, value)
            except Exception:
                pass
        return obj


def add_track_with_source(owner: Any, path: Path | str) -> VideoTrack:
    path = Path(path)
    _safe_call(getattr(owner, "_register_screenstudio_real_recording_candidate", None), path, reason="track import")
    tid = _next_track_id(owner)
    track = VideoTrack(id=tid, source_path=path)
    hdr_probe = getattr(owner, "_probe_track_hdr_info", None)
    hdr_info = _safe_call(hdr_probe, path)
    if hdr_info is not None:
        try:
            track.hdr_info = hdr_info
        except Exception:
            pass
    _owner_track_list(owner, "_tracks").append(track)
    _safe_call(getattr(owner, "_insert_track_widget", None), track)
    _safe_call(getattr(owner, "_start_thumbnail_extraction", None), track)
    _safe_call(getattr(owner, "_set_active_track", None), tid)
    _refresh_after_timeline_change(owner, render_immediately=False)
    _ensure_video_clips(track)
    for clip in getattr(track, "clips", []) or []:
        _safe_call(getattr(owner, "_load_screenstudio_cursor_sidecar_for_clip", None), clip)
        _safe_call(
            getattr(owner, "_maybe_apply_default_screenstudio_polish_to_clip", None),
            track,
            clip,
            reason="track import",
        )
    row = _row_for_track(owner, tid)
    if row is not None:
        _safe_call(getattr(row, "update", None))
    _refresh_after_timeline_change(owner, render_immediately=False)
    _safe_call(getattr(owner, "_try_apply_startup_template_if_ready", None), "video import")
    return track


def populate_video_track(owner: Any, track_id: int, path: Path | str) -> VideoTrack | Any | None:
    track = _find_video_track(owner, track_id)
    if track is None or getattr(track, "source_path", None) is not None:
        return None
    path = Path(path)
    track.source_path = path
    hdr_probe = getattr(owner, "_probe_track_hdr_info", None)
    hdr_info = _safe_call(hdr_probe, path)
    if hdr_info is not None:
        try:
            track.hdr_info = hdr_info
        except Exception:
            pass
    row = _row_for_track(owner, track_id)
    if row is not None:
        _safe_call(getattr(row, "update", None))
    _safe_call(getattr(owner, "_start_thumbnail_extraction", None), track)
    _refresh_after_timeline_change(owner, render_immediately=False)
    _ensure_video_clips(track)
    for clip in getattr(track, "clips", []) or []:
        _safe_call(
            getattr(owner, "_maybe_apply_default_screenstudio_polish_to_clip", None),
            track,
            clip,
            reason="track populate",
        )
    if row is not None:
        _safe_call(getattr(row, "update", None))
    _refresh_after_timeline_change(owner, render_immediately=False)
    if int(track_id) == getattr(owner, "_active_track_id", None):
        _safe_call(getattr(owner, "_refresh_workbench", None))
    _safe_call(getattr(owner, "_try_apply_startup_template_if_ready", None), "video import")
    return track


def append_clip_to_track(
    owner: Any,
    track: VideoTrack | Any,
    path: Path | str,
    *,
    duration_ms: int | None = None,
) -> VideoClip | None:
    path = Path(path)
    duration = int(duration_ms or 0)
    if duration <= 0:
        duration = int(probe_video_duration_ms(path) or 0)
    if duration <= 0:
        return None
    clips = getattr(track, "clips", None)
    if not isinstance(clips, list):
        track.clips = []
        clips = track.clips
    tail_ms = max((int(getattr(c, "timeline_out_ms", 0) or 0) for c in clips), default=0)
    clip = VideoClip(
        id=_next_video_clip_id(owner),
        source_path=path,
        source_duration_ms=duration,
        timeline_in_ms=tail_ms,
        source_in_ms=0,
        source_out_ms=duration,
        node_graph=NodeGraph.default(),
    )
    clips.append(clip)
    try:
        track.clips_explicit = True
    except Exception:
        pass
    _safe_call(
        getattr(owner, "_maybe_apply_default_screenstudio_polish_to_clip", None),
        track,
        clip,
        reason="clip append",
    )
    _safe_call(getattr(owner, "_start_thumbnail_extraction_for_clip", None), clip, int(getattr(track, "id", 0) or 0))
    _refresh_after_timeline_change(owner, render_immediately=False)
    _flash_track_row(owner, int(getattr(track, "id", 0) or 0), "cut", tail_ms)
    _safe_call(getattr(owner, "_register_change", None), "append clip")
    _safe_call(getattr(owner, "_try_apply_startup_template_if_ready", None), "video import")
    return clip


def _mark_image_media_object(obj: Any) -> Any:
    try:
        setattr(obj, "track_type", "image")
        setattr(obj, "program_output", True)
    except Exception:
        pass
    return obj


def _image_clip(
    owner: Any,
    path: Path,
    *,
    start_ms: int,
    duration_ms: int | None = None,
) -> VideoClip:
    duration = max(100, int(duration_ms or DEFAULT_IMAGE_DURATION_MS))
    clip = VideoClip(
        id=_next_video_clip_id(owner),
        source_path=path,
        source_duration_ms=duration,
        timeline_in_ms=max(0, int(start_ms or 0)),
        source_in_ms=0,
        source_out_ms=duration,
        node_graph=NodeGraph.default(),
    )
    return _mark_image_media_object(clip)


def add_image_track_with_source(
    owner: Any,
    path: Path | str,
    *,
    start_ms: int | None = None,
    duration_ms: int | None = None,
) -> VideoTrack:
    path = Path(path)
    tid = _next_track_id(owner)
    if start_ms is None:
        start_ms = _current_playhead_ms(owner)
    clip = _image_clip(owner, path, start_ms=max(0, int(start_ms or 0)), duration_ms=duration_ms)
    track = VideoTrack(id=tid, source_path=None, clips=[clip])
    _mark_image_media_object(track)
    track.clips_explicit = True
    track.duration_ms = int(getattr(clip, "timeline_out_ms", 0) or 0)
    try:
        track.label = "Image"
    except Exception:
        pass
    _owner_track_list(owner, "_tracks").append(track)
    _safe_call(getattr(owner, "_insert_track_widget", None), track)
    _safe_call(getattr(owner, "_start_thumbnail_extraction_for_clip", None), clip, tid)
    _safe_call(getattr(owner, "_set_active_track", None), tid)
    _refresh_after_timeline_change(owner, render_immediately=False)
    _flash_track_row(owner, tid, "image", int(getattr(clip, "timeline_in_ms", 0) or 0))
    _safe_call(getattr(owner, "_register_change", None), "add image track")
    _safe_call(getattr(owner, "_try_apply_startup_template_if_ready", None), "image import")
    return track


def append_image_clip_to_track(
    owner: Any,
    track: VideoTrack | Any,
    path: Path | str,
    *,
    start_ms: int | None = None,
    duration_ms: int | None = None,
) -> VideoClip | None:
    path = Path(path)
    clips = getattr(track, "clips", None)
    if not isinstance(clips, list):
        track.clips = []
        clips = track.clips
    tail_ms = max((int(getattr(c, "timeline_out_ms", 0) or 0) for c in clips), default=0)
    clip_start_ms = tail_ms if start_ms is None else max(0, int(start_ms or 0))
    clip = _image_clip(owner, path, start_ms=clip_start_ms, duration_ms=duration_ms)
    clips.append(clip)
    _mark_image_media_object(track)
    try:
        track.source_path = None
        track.clips_explicit = True
        track.duration_ms = max(int(getattr(track, "duration_ms", 0) or 0), int(clip.timeline_out_ms))
    except Exception:
        pass
    _safe_call(getattr(owner, "_start_thumbnail_extraction_for_clip", None), clip, int(getattr(track, "id", 0) or 0))
    _refresh_after_timeline_change(owner, render_immediately=False)
    _flash_track_row(owner, int(getattr(track, "id", 0) or 0), "image", clip_start_ms)
    _safe_call(getattr(owner, "_register_change", None), "append image clip")
    _safe_call(getattr(owner, "_try_apply_startup_template_if_ready", None), "image import")
    return clip


def add_audio_track_with_source(
    owner: Any,
    path: Path | str,
    *,
    open_editor: bool = False,
    duration_ms: int | None = None,
) -> AudioTrack | None:
    path = Path(path)
    duration = int(duration_ms or 0)
    if duration <= 0:
        duration = int(probe_audio_duration_ms(path) or 0)
    if duration <= 0:
        return None
    tid = _next_track_id(owner)
    clip = AudioClip(
        id=_next_audio_clip_id(owner),
        source_path=path,
        duration_ms=duration,
        trim_end_ms=duration,
    )
    track = AudioTrack(id=tid, clips=[clip])
    _owner_track_list(owner, "_audio_tracks").append(track)
    _safe_call(getattr(owner, "_insert_audio_track_widget", None), track)
    mixer = getattr(owner, "_audio_mixer", None)
    _safe_call(getattr(mixer, "add_track", None), track)
    _safe_call(getattr(owner, "_start_waveform_extraction", None), clip)
    _refresh_after_timeline_change(owner)
    _safe_call(getattr(owner, "_try_apply_startup_template_if_ready", None), "audio import")
    if open_editor:
        _safe_call(getattr(owner, "_open_sound_editor", None), tid, int(getattr(clip, "id", 0) or 0))
    return track


def populate_audio_track(
    owner: Any,
    track_id: int,
    path: Path | str,
    *,
    duration_ms: int | None = None,
) -> AudioClip | None:
    track = _find_audio_track(owner, track_id)
    if track is None or bool(getattr(track, "is_loaded", False)):
        return None
    path = Path(path)
    duration = int(duration_ms or 0)
    if duration <= 0:
        duration = int(probe_audio_duration_ms(path) or 0)
    if duration <= 0:
        return None
    clip = AudioClip(
        id=_next_audio_clip_id(owner),
        source_path=path,
        duration_ms=duration,
        trim_end_ms=duration,
    )
    clips = getattr(track, "clips", None)
    if not isinstance(clips, list):
        track.clips = []
        clips = track.clips
    clips.append(clip)
    _touch_audio_track_ui(owner, track, clip)
    _refresh_after_timeline_change(owner)
    _safe_call(getattr(owner, "_try_apply_startup_template_if_ready", None), "audio import")
    return clip


def append_audio_clip_to_track(
    owner: Any,
    track: AudioTrack | Any,
    path: Path | str,
    *,
    duration_ms: int | None = None,
) -> AudioClip | None:
    path = Path(path)
    duration = int(duration_ms or 0)
    if duration <= 0:
        duration = int(probe_audio_duration_ms(path) or 0)
    if duration <= 0:
        return None
    tail = 0
    extent = getattr(track, "extent_ms", None)
    if callable(extent):
        try:
            tail = int(extent())
        except Exception:
            tail = 0
    else:
        clips = getattr(track, "clips", []) or []
        for clip in clips:
            length = int(getattr(clip, "effective_length_ms", getattr(clip, "duration_ms", 0)) or 0)
            tail = max(tail, int(getattr(clip, "offset_ms", 0) or 0) + length)
    clip = AudioClip(
        id=_next_audio_clip_id(owner),
        source_path=path,
        duration_ms=duration,
        offset_ms=tail,
        trim_end_ms=duration,
    )
    clips = getattr(track, "clips", None)
    if not isinstance(clips, list):
        track.clips = []
        clips = track.clips
    clips.append(clip)
    _touch_audio_track_ui(owner, track, clip)
    _refresh_after_timeline_change(owner)
    _safe_call(getattr(owner, "_try_apply_startup_template_if_ready", None), "audio import")
    return clip


def ensure_performance_source_track(owner: Any) -> VideoTrack | Any:
    try:
        from app.vtuber.performance_source import is_performance_source_track
    except Exception:
        is_performance_source_track = lambda track: bool(getattr(track, "performance_source", False))
    for track in getattr(owner, "_tracks", []) or []:
        try:
            if is_performance_source_track(track):
                return track
        except Exception:
            if bool(getattr(track, "performance_source", False)):
                return track
    track = VideoTrack(id=_next_track_id(owner))
    _mark_performance_source(track)
    track.source_path = None
    track.clips = []
    track.clips_explicit = True
    _owner_track_list(owner, "_tracks").append(track)
    _safe_call(getattr(owner, "_insert_track_widget", None), track)
    return track


def add_performance_source_clip(
    owner: Any,
    path: Path | str,
    start_ms: int | None = None,
    *,
    duration_ms: int | None = None,
) -> VideoClip | None:
    path = Path(path)
    if not is_video_path(path):
        return None
    _register_in_media_pool(owner, path, performance_source=True)
    duration = int(duration_ms or 0)
    if duration <= 0:
        duration = int(probe_video_duration_ms(path) or 0)
    if duration <= 0:
        return None
    if start_ms is None:
        start_ms = _current_playhead_ms(owner)
    track = ensure_performance_source_track(owner)
    clips = getattr(track, "clips", None)
    if not isinstance(clips, list):
        track.clips = []
        clips = track.clips
    clip = VideoClip(
        id=_next_video_clip_id(owner),
        source_path=path,
        source_duration_ms=duration,
        timeline_in_ms=max(0, int(start_ms or 0)),
        source_in_ms=0,
        source_out_ms=duration,
        node_graph=NodeGraph.default(),
    )
    _mark_performance_source(clip)
    clips.append(clip)
    clips.sort(key=lambda row: int(getattr(row, "timeline_in_ms", 0) or 0))
    try:
        track.clips_explicit = True
    except Exception:
        pass
    _safe_call(getattr(owner, "_start_thumbnail_extraction_for_clip", None), clip, int(getattr(track, "id", 0) or 0))
    _safe_call(getattr(owner, "_set_active_track", None), int(getattr(track, "id", 0) or 0))
    _refresh_after_timeline_change(owner)
    _flash_track_row(owner, int(getattr(track, "id", 0) or 0), "drop", int(getattr(clip, "timeline_in_ms", 0) or 0))
    _safe_call(getattr(owner, "_register_change", None), "add performance source")
    _safe_call(
        getattr(owner, "_record_editor_action", None),
        "vtuber.performance_source.add",
        path=str(path),
        start_ms=int(getattr(clip, "timeline_in_ms", 0) or 0),
        duration_ms=int(duration),
    )
    return clip


def dispatch_import_decision(owner: Any, decision: MediaImportDecision) -> bool:
    if not decision.handled or decision.path is None:
        return False
    path = decision.path
    if decision.route == ROUTE_VRM_AVATAR:
        _register_in_media_pool(owner, path)
        _safe_call(getattr(owner, "_open_vrm_media_in_vtuber_studio", None), str(path))
        return True
    if decision.route == ROUTE_MMD:
        add = getattr(owner, "_add_mmd_asset_to_timeline", None)
        if decision.start_ms is None:
            _safe_call(add, list(decision.paths) if len(decision.paths) > 1 else path)
        else:
            _safe_call(add, list(decision.paths) if len(decision.paths) > 1 else path, start_ms=int(decision.start_ms))
        return True
    if decision.route == ROUTE_MOTION:
        add = getattr(owner, "_import_motion_actor_from_path", None)
        if callable(add):
            result = _safe_call(add, path, start_ms=decision.start_ms)
            return result is not False
        return False
    if decision.route == ROUTE_AR_PBR:
        add = getattr(owner, "_add_ar_pbr_asset_to_preview", None)
        kwargs: dict[str, Any] = {}
        if decision.image_point is not None:
            kwargs["image_point"] = decision.image_point
        if decision.start_ms is not None:
            kwargs["start_ms"] = max(0, int(decision.start_ms))
        _safe_call(add, path, **kwargs)
        return True
    if decision.route == ROUTE_PERFORMANCE_SOURCE:
        add = getattr(owner, "_add_performance_source_clip", None)
        if callable(add):
            _safe_call(add, path, decision.start_ms)
        else:
            add_performance_source_clip(owner, path, decision.start_ms)
        return True
    if decision.route == ROUTE_VIDEO:
        if decision.target == TARGET_VIDEO_ROW and decision.track_id is not None:
            return on_media_dropped_on_video_row(owner, decision.track_id, path)
        add = getattr(owner, "_add_track_with_source", None)
        if callable(add):
            _safe_call(add, path)
        else:
            add_track_with_source(owner, path)
        return True
    if decision.route == ROUTE_IMAGE:
        if decision.target == TARGET_VIDEO_ROW and decision.track_id is not None:
            return on_media_dropped_on_video_row(owner, decision.track_id, path)
        add = getattr(owner, "_add_image_track_with_source", None)
        if callable(add):
            _safe_call(add, path)
        else:
            add_image_track_with_source(owner, path, start_ms=decision.start_ms)
        return True
    if decision.route == ROUTE_AUDIO:
        if decision.target == TARGET_AUDIO_ROW and decision.track_id is not None:
            return on_media_dropped_on_audio_row(owner, decision.track_id, path)
        add = getattr(owner, "_add_audio_track_with_source", None)
        if callable(add):
            _safe_call(add, path, open_editor=decision.open_audio_editor)
        else:
            add_audio_track_with_source(owner, path, open_editor=decision.open_audio_editor)
        return True
    return False


def add_timeline_media_from_mime(owner: Any, mime: Any, *, open_audio_editor: bool = False) -> bool:
    decision = route_mime_drop(
        owner,
        mime,
        target=TARGET_TIMELINE,
        start_ms=_current_playhead_ms(owner),
        image_point=(0.5, 0.62),
        open_audio_editor=open_audio_editor,
    )
    return dispatch_import_decision(owner, decision)


def on_media_dropped_on_video_row(owner: Any, track_id: int, path: Path | str) -> bool:
    path = Path(path)
    _register_in_media_pool(owner, path)
    if path.suffix.casefold() == ".tgmotion":
        add = getattr(owner, "_import_motion_actor_from_path", None)
        return bool(_safe_call(add, path, start_ms=_current_playhead_ms(owner))) if callable(add) else False
    try:
        from app.mmd.project_tracks import is_mmd_asset_path

        if is_mmd_asset_path(path):
            _safe_call(getattr(owner, "_add_mmd_asset_to_timeline", None), path)
            return True
    except Exception:
        pass
    try:
        from app.ar_pbr.project_tracks import is_ar_pbr_asset_path

        if path.suffix.casefold() != ".vrm" and is_ar_pbr_asset_path(path):
            _safe_call(
                getattr(owner, "_add_ar_pbr_asset_to_preview", None),
                path,
                image_point=(0.5, 0.62),
                start_ms=_current_playhead_ms(owner),
            )
            return True
    except Exception:
        pass
    if is_video_path(path):
        marks = getattr(owner, "_media_pool_marks_performance_source", None)
        if callable(marks) and bool(_safe_call(marks, path)):
            add = getattr(owner, "_add_performance_source_clip", None)
            if callable(add):
                _safe_call(add, path, _current_playhead_ms(owner))
            else:
                add_performance_source_clip(owner, path, _current_playhead_ms(owner))
            return True
        track = _find_video_track(owner, track_id)
        if track is not None and getattr(track, "source_path", None) is None and not getattr(track, "clips", []):
            populate = getattr(owner, "_populate_video_track", None)
            if callable(populate):
                _safe_call(populate, track_id, path)
            else:
                populate_video_track(owner, track_id, path)
        elif track is not None and getattr(track, "clips", []):
            append = getattr(owner, "_append_clip_to_track", None)
            if callable(append):
                _safe_call(append, track, path)
            else:
                append_clip_to_track(owner, track, path)
        else:
            add = getattr(owner, "_add_track_with_source", None)
            if callable(add):
                _safe_call(add, path)
            else:
                add_track_with_source(owner, path)
        return True
    if is_image_path(path):
        track = _find_video_track(owner, track_id)
        if track is not None and (
            str(getattr(track, "track_type", "") or "").casefold() == "image"
            or not getattr(track, "clips", [])
        ):
            append_image_clip_to_track(owner, track, path)
        else:
            add = getattr(owner, "_add_image_track_with_source", None)
            if callable(add):
                _safe_call(add, path)
            else:
                add_image_track_with_source(owner, path, start_ms=_current_playhead_ms(owner))
        return True
    if is_audio_path(path):
        add = getattr(owner, "_add_audio_track_with_source", None)
        if callable(add):
            _safe_call(add, path)
        else:
            add_audio_track_with_source(owner, path)
        return True
    return False


def on_media_dropped_on_audio_row(owner: Any, track_id: int, path: Path | str) -> bool:
    path = Path(path)
    _register_in_media_pool(owner, path)
    if path.suffix.casefold() == ".tgmotion":
        add = getattr(owner, "_import_motion_actor_from_path", None)
        return bool(_safe_call(add, path, start_ms=_current_playhead_ms(owner))) if callable(add) else False
    try:
        from app.mmd.project_tracks import is_mmd_asset_path

        if is_mmd_asset_path(path):
            _safe_call(getattr(owner, "_add_mmd_asset_to_timeline", None), path)
            return True
    except Exception:
        pass
    try:
        from app.ar_pbr.project_tracks import is_ar_pbr_asset_path

        if path.suffix.casefold() != ".vrm" and is_ar_pbr_asset_path(path):
            _safe_call(
                getattr(owner, "_add_ar_pbr_asset_to_preview", None),
                path,
                image_point=(0.5, 0.62),
                start_ms=_current_playhead_ms(owner),
            )
            return True
    except Exception:
        pass
    if is_video_path(path):
        marks = getattr(owner, "_media_pool_marks_performance_source", None)
        if callable(marks) and bool(_safe_call(marks, path)):
            add = getattr(owner, "_add_performance_source_clip", None)
            if callable(add):
                _safe_call(add, path, _current_playhead_ms(owner))
            else:
                add_performance_source_clip(owner, path, _current_playhead_ms(owner))
            return True
        add = getattr(owner, "_add_track_with_source", None)
        if callable(add):
            _safe_call(add, path)
        else:
            add_track_with_source(owner, path)
        return True
    if is_image_path(path):
        add = getattr(owner, "_add_image_track_with_source", None)
        if callable(add):
            _safe_call(add, path)
        else:
            add_image_track_with_source(owner, path, start_ms=_current_playhead_ms(owner))
        return True
    if not is_audio_path(path):
        return False
    track = _find_audio_track(owner, track_id)
    if track is None:
        add = getattr(owner, "_add_audio_track_with_source", None)
        if callable(add):
            _safe_call(add, path, open_editor=True)
        else:
            add_audio_track_with_source(owner, path, open_editor=True)
        return True
    if not bool(getattr(track, "is_loaded", False)):
        populate = getattr(owner, "_populate_audio_track", None)
        if callable(populate):
            _safe_call(populate, track_id, path)
        else:
            populate_audio_track(owner, track_id, path)
        return True
    append = getattr(owner, "_append_audio_clip_to_track", None)
    if callable(append):
        _safe_call(append, track, path)
    else:
        append_audio_clip_to_track(owner, track, path)
    return True


def on_media_pool_item_added(owner: Any, path: Path | str) -> MediaImportDecision:
    path = Path(path)
    _safe_call(getattr(owner, "_register_screenstudio_real_recording_candidate", None), path, reason="media pool import")
    if path.suffix.casefold() == ".vrm":
        return MediaImportDecision(route=ROUTE_VRM_AVATAR, paths=(path,), target="media_pool")
    try:
        from app.ar_pbr.project_tracks import is_ar_pbr_asset_path

        if is_ar_pbr_asset_path(path):
            _safe_call(getattr(owner, "_schedule_ar_pbr_descriptor_prewarm", None), path)
            return MediaImportDecision(route=ROUTE_AR_PBR, paths=(path,), target="media_pool")
    except Exception:
        pass
    if is_video_path(path):
        marks = getattr(owner, "_media_pool_marks_performance_source", None)
        if callable(marks) and bool(_safe_call(marks, path)):
            return MediaImportDecision(route=ROUTE_PERFORMANCE_SOURCE, paths=(path,), target="media_pool")
        return MediaImportDecision(route=ROUTE_VIDEO, paths=(path,), target="media_pool")
    if is_image_path(path):
        return MediaImportDecision(route=ROUTE_IMAGE, paths=(path,), target="media_pool")
    if is_audio_path(path):
        return MediaImportDecision(route=ROUTE_AUDIO, paths=(path,), target="media_pool")
    try:
        from app.mmd.project_tracks import is_mmd_asset_path

        if is_mmd_asset_path(path):
            return MediaImportDecision(route=ROUTE_MMD, paths=(path,), target="media_pool")
    except Exception:
        pass
    return MediaImportDecision(target="media_pool")


def on_media_pool_selection_changed(owner: Any, path: Path | str) -> AudioClip | None:
    try:
        media_path = Path(path).expanduser().resolve()
    except Exception:
        return None
    if not media_path.is_file() or not is_audio_path(media_path):
        return None
    duration = int(probe_audio_duration_ms(media_path) or 0)
    store = getattr(owner, "_sound_edit_state_store", None)
    if store is None:
        try:
            from app.sound_edit_state_store import SoundEditStateStore

            store = SoundEditStateStore()
            owner._sound_edit_state_store = store
        except Exception:
            store = None
    clip = None
    media_clip = getattr(store, "media_clip", None)
    if callable(media_clip):
        clip = _safe_call(media_clip, media_path, duration)
    if clip is None:
        clip = AudioClip(
            id=_next_audio_clip_id(owner),
            source_path=media_path,
            duration_ms=duration,
            trim_end_ms=duration,
        )
    _safe_call(getattr(owner, "_start_waveform_extraction", None), clip)
    panel = getattr(owner, "_workbench_panel", None)
    set_source = getattr(panel, "set_audio_source_clip", None)
    if callable(set_source):
        _safe_call(set_source, clip, source_path=media_path)
        try:
            owner._node_grade_target = None
        except Exception:
            pass
        _safe_call(getattr(owner, "_sync_color_panel", None))
    return clip


__all__ = [
    "MediaImportDecision",
    "ROUTE_NONE",
    "ROUTE_VRM_AVATAR",
    "ROUTE_MMD",
    "ROUTE_MOTION",
    "ROUTE_AR_PBR",
    "ROUTE_PERFORMANCE_SOURCE",
    "ROUTE_VIDEO",
    "ROUTE_IMAGE",
    "ROUTE_AUDIO",
    "TARGET_TIMELINE",
    "TARGET_WINDOW",
    "TARGET_TRACKS_HOST",
    "TARGET_PREVIEW",
    "TARGET_VIDEO_ROW",
    "TARGET_AUDIO_ROW",
    "accepts_mime_drop",
    "add_audio_track_with_source",
    "add_image_track_with_source",
    "add_performance_source_clip",
    "add_timeline_media_from_mime",
    "add_track_with_source",
    "append_audio_clip_to_track",
    "append_clip_to_track",
    "append_image_clip_to_track",
    "ar_pbr_paths_from_mime",
    "dispatch_import_decision",
    "ensure_performance_source_track",
    "mmd_paths_from_mime",
    "motion_project_paths_from_mime",
    "on_media_dropped_on_audio_row",
    "on_media_dropped_on_video_row",
    "on_media_pool_item_added",
    "on_media_pool_selection_changed",
    "performance_source_paths_from_mime",
    "populate_audio_track",
    "populate_video_track",
    "route_audio_row_drop",
    "route_mime_drop",
    "route_preview_drop",
    "route_tracks_host_drop",
    "route_video_row_drop",
    "timeline_media_paths_from_mime",
    "timeline_start_ms_from_drop_x",
    "vrm_avatar_paths_from_mime",
]
