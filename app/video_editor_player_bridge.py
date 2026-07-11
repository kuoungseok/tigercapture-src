from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

from PySide6.QtWidgets import QMessageBox

from app.i18n import tr


NESTED_AUDIO_PREVIEW_TRACK_ID = -9001
VIDEO_EMBEDDED_AUDIO_PREVIEW_TRACK_ID = -9002


def _on_player_error(self, msg: str) -> None:
    import sys as _sys

    print(f"[veditor] player error: {msg}", file=_sys.stderr, flush=True)
    QMessageBox.warning(self, tr("veditor.title"), msg)


def _on_media_status(self, status) -> None:
    import sys as _sys

    print(f"[veditor] media status: {status}", file=_sys.stderr, flush=True)


def _call(obj: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(obj, name, None)
    if callable(method):
        return method(*args, **kwargs)
    return None


def _values(mapping: Any) -> list[Any]:
    if mapping is None:
        return []
    values = getattr(mapping, "values", None)
    if callable(values):
        return list(values())
    return list(mapping or [])


def _format_ms(ms: int) -> str:
    ms = max(0, int(ms))
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _playing_state(state: Any) -> bool:
    try:
        from app.simple_video_player import PlayerState

        return state is PlayerState.PLAYING
    except Exception:
        return getattr(state, "name", None) == "PLAYING"


def _clip_extent_ms(clip: Any) -> int:
    return int(getattr(clip, "offset_ms", 0) or 0) + int(
        getattr(clip, "effective_length_ms", 0) or 0
    )


def _audio_track_extent_ms(track: Any) -> int:
    extent = getattr(track, "extent_ms", None)
    if callable(extent):
        return int(extent())
    return max((_clip_extent_ms(clip) for clip in getattr(track, "clips", []) or []), default=0)


def _actor_tracks_extent_ms(tracks: Any) -> int:
    return max(
        (
            int(getattr(clip, "end_ms", 0) or 0)
            for track in tracks or []
            for clip in getattr(track, "clips", []) or []
        ),
        default=0,
    )


def _dict_track_extent_ms(tracks: Any) -> int:
    extents: list[int] = []
    for track in tracks or []:
        getter = getattr(track, "get", None)
        if callable(getter):
            extents.append(int(getter("end_ms", 0) or 0))
    return max(extents, default=0)


def collect_nested_audio_preview_clips(owner: Any) -> list[Any]:
    collected: list[Any] = []
    next_id = -100000

    def _walk(clips: list[Any], base_ms: int = 0) -> None:
        nonlocal next_id
        for clip in clips or []:
            clip_base = int(base_ms) + int(getattr(clip, "timeline_in_ms", 0) or 0)
            for audio_lane in getattr(clip, "nested_audio_tracks", []) or []:
                for audio_clip in audio_lane or []:
                    copied = copy.deepcopy(audio_clip)
                    copied.id = next_id
                    next_id -= 1
                    copied.offset_ms = clip_base + int(getattr(audio_clip, "offset_ms", 0) or 0)
                    collected.append(copied)
            nested_tracks = clip.nested_tracks() if hasattr(clip, "nested_tracks") else []
            for child_track in nested_tracks:
                _walk(list(child_track or []), clip_base)

    for track in getattr(owner, "_tracks", []) or []:
        _walk(list(getattr(track, "clips", []) or []), 0)
    return collected


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _path_key(path: Any) -> str:
    if path in (None, ""):
        return ""
    try:
        return str(Path(path).resolve()).casefold()
    except Exception:
        return str(path).casefold()


def _audio_clip_signature(clip: Any) -> tuple[str, int, int, int]:
    return (
        _path_key(getattr(clip, "source_path", None)),
        _int(getattr(clip, "offset_ms", 0)),
        _int(getattr(clip, "trim_start_ms", 0)),
        _int(getattr(clip, "effective_trim_end_ms", getattr(clip, "trim_end_ms", 0))),
    )


def _existing_audio_preview_signatures(owner: Any) -> tuple[set[int], set[tuple[str, int, int, int]]]:
    clip_ids: set[int] = set()
    signatures: set[tuple[str, int, int, int]] = set()
    for track in getattr(owner, "_audio_tracks", []) or []:
        for clip in getattr(track, "clips", []) or []:
            cid = getattr(clip, "id", None)
            if cid is not None:
                clip_ids.add(_int(cid))
            sig = _audio_clip_signature(clip)
            if sig[0]:
                signatures.add(sig)
    return clip_ids, signatures


def _video_clip_audio_fields(track: Any, clip: Any) -> tuple[Path | None, int, int, int, int]:
    source = getattr(clip, "source_path", None)
    if source in (None, ""):
        source = getattr(track, "source_path", None)
    if source in (None, ""):
        return None, 0, 0, 0, 0
    try:
        source_path = Path(source)
    except Exception:
        return None, 0, 0, 0, 0
    timeline_in = _int(
        getattr(clip, "timeline_in_ms", getattr(track, "offset_ms", 0)),
        _int(getattr(track, "offset_ms", 0)),
    )
    source_in = max(0, _int(getattr(clip, "source_in_ms", 0)))
    source_duration = max(
        0,
        _int(
            getattr(
                clip,
                "source_duration_ms",
                getattr(track, "duration_ms", 0),
            )
        ),
    )
    source_out = _int(
        getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 0)),
        0,
    )
    if source_out <= 0:
        source_out = source_duration
    if source_out <= source_in:
        length = _int(getattr(clip, "effective_length_ms", 0), 0)
        if length <= 0:
            length = max(0, _int(getattr(track, "duration_ms", 0), 0))
        source_out = source_in + length
    duration = max(source_duration, source_out)
    return source_path, timeline_in, source_in, source_out, duration


def collect_video_embedded_audio_preview_clips(owner: Any) -> list[Any]:
    from app.audio_tracks import AudioClip

    linked_audio_ids, existing_signatures = _existing_audio_preview_signatures(owner)
    collected: list[Any] = []
    next_id = -200000
    for track in getattr(owner, "_tracks", []) or []:
        clips = list(getattr(track, "clips", []) or [])
        if not clips and getattr(track, "source_path", None) is not None:
            clips = [track]
        for clip in clips:
            linked_id = getattr(clip, "linked_audio_id", None)
            if linked_id is not None and _int(linked_id, -1) in linked_audio_ids:
                continue
            source_path, timeline_in, source_in, source_out, duration = _video_clip_audio_fields(track, clip)
            if source_path is None or duration <= 0 or source_out <= source_in:
                continue
            signature = (_path_key(source_path), timeline_in, source_in, source_out)
            if signature in existing_signatures:
                continue
            audio_clip = AudioClip(
                id=next_id,
                source_path=source_path,
                duration_ms=duration,
                offset_ms=timeline_in,
                trim_start_ms=source_in,
                trim_end_ms=source_out,
            )
            setattr(audio_clip, "preview_embedded_video_audio", True)
            collected.append(audio_clip)
            next_id -= 1
    return collected


def sync_video_embedded_audio_preview_track(
    owner: Any,
    *,
    preview_track_id: int = VIDEO_EMBEDDED_AUDIO_PREVIEW_TRACK_ID,
    audio_track_factory: Callable[..., Any] | None = None,
) -> int:
    clips = collect_video_embedded_audio_preview_clips(owner)
    mixer = getattr(owner, "_audio_mixer", None)
    if mixer is None:
        return max((_clip_extent_ms(clip) for clip in clips), default=0)
    if not clips:
        _call(mixer, "remove_track", preview_track_id)
        return 0
    if audio_track_factory is None:
        from app.audio_tracks import AudioTrack

        audio_track_factory = AudioTrack
    track = audio_track_factory(
        id=preview_track_id,
        clips=clips,
        label="Embedded video audio preview",
    )
    _call(mixer, "update_track", track)
    return _audio_track_extent_ms(track)


def sync_nested_audio_preview_track(
    owner: Any,
    *,
    preview_track_id: int = NESTED_AUDIO_PREVIEW_TRACK_ID,
    audio_track_factory: Callable[..., Any] | None = None,
) -> int:
    clips = collect_nested_audio_preview_clips(owner)
    mixer = getattr(owner, "_audio_mixer", None)
    if mixer is None:
        return max((_clip_extent_ms(clip) for clip in clips), default=0)
    if not clips:
        _call(mixer, "remove_track", preview_track_id)
        return 0
    if audio_track_factory is None:
        from app.audio_tracks import AudioTrack

        audio_track_factory = AudioTrack
    track = audio_track_factory(
        id=preview_track_id,
        clips=clips,
        label="Nested audio preview",
    )
    _call(mixer, "update_track", track)
    return _audio_track_extent_ms(track)


def sync_ar_pbr_tracks_to_player(owner: Any) -> None:
    player = getattr(owner, "_player", None)
    if player is not None and hasattr(player, "set_ar_pbr_tracks"):
        player.set_ar_pbr_tracks(getattr(owner, "_ar_pbr_tracks", []) or [])


def sync_mmd_tracks_to_player(owner: Any) -> None:
    player = getattr(owner, "_player", None)
    if player is not None and hasattr(player, "set_mmd_tracks"):
        player.set_mmd_tracks(getattr(owner, "_mmd_tracks", []) or [])


def sync_actor_tracks_to_player(owner: Any) -> None:
    player = getattr(owner, "_player", None)
    if player is None:
        return
    if hasattr(player, "set_spine_actor_tracks"):
        player.set_spine_actor_tracks(getattr(owner, "_spine_actor_tracks", []) or [])
    if hasattr(player, "set_live2d_actor_tracks"):
        player.set_live2d_actor_tracks(getattr(owner, "_live2d_actor_tracks", []) or [])


def _call_owner_sync(owner: Any, name: str, fallback: Callable[[Any], None]) -> None:
    hook = getattr(owner, name, None)
    if callable(hook):
        hook()
    else:
        fallback(owner)


def repaint_timeline_rows(owner: Any) -> None:
    for row in _values(getattr(owner, "_track_rows", None)):
        _call(row, "update")
    for row in _values(getattr(owner, "_audio_rows", None)):
        _call(row, "update")
    for row in getattr(owner, "_actor_lane_rows", []) or []:
        _call(row, "update")
    for row in getattr(owner, "_live2d_lane_rows", []) or []:
        _call(row, "update")
    for row in getattr(owner, "_ar_pbr_lane_rows", []) or []:
        _call(row, "update")
    for row in getattr(owner, "_mmd_lane_rows", []) or []:
        _call(row, "update")


def refresh_player_tracks(
    owner: Any,
    *,
    render_immediately: bool = True,
    sync_actor_tracks: bool | None = None,
) -> None:
    nested_audio_end = sync_nested_audio_preview_track(owner)
    embedded_audio_end = sync_video_embedded_audio_preview_track(owner)
    extra = max(
        (_audio_track_extent_ms(track) for track in getattr(owner, "_audio_tracks", []) or []),
        default=0,
    )
    spine_end = _actor_tracks_extent_ms(getattr(owner, "_spine_actor_tracks", []) or [])
    live2d_end = _actor_tracks_extent_ms(getattr(owner, "_live2d_actor_tracks", []) or [])
    ar_pbr_end = _dict_track_extent_ms(getattr(owner, "_ar_pbr_tracks", []) or [])
    mmd_end = _dict_track_extent_ms(getattr(owner, "_mmd_tracks", []) or [])
    extra = max(extra, nested_audio_end, embedded_audio_end, spine_end, live2d_end, ar_pbr_end, mmd_end)

    player = getattr(owner, "_player", None)
    if player is not None and hasattr(player, "set_project_settings"):
        player.set_project_settings(getattr(owner, "_project_settings", {}) or {})
    _call_owner_sync(owner, "_sync_ar_pbr_tracks_to_player", sync_ar_pbr_tracks_to_player)
    _call_owner_sync(owner, "_sync_mmd_tracks_to_player", sync_mmd_tracks_to_player)
    actor_hook = getattr(owner, "_sync_actor_tracks_to_player", None)
    if sync_actor_tracks is True or (sync_actor_tracks is None and callable(actor_hook)):
        if callable(actor_hook):
            actor_hook()
        else:
            sync_actor_tracks_to_player(owner)
    _call(owner, "_refresh_preview_canvas_interaction_hook")

    if player is not None and hasattr(player, "refresh_tracks"):
        try:
            player.refresh_tracks(
                getattr(owner, "_tracks", []) or [],
                extra_duration_ms=extra,
                render_immediately=render_immediately,
            )
        except TypeError:
            player.refresh_tracks(getattr(owner, "_tracks", []) or [], extra_duration_ms=extra)

    _call(owner, "_update_preview_placeholder")
    repaint_timeline_rows(owner)
    _call(owner, "_refresh_proxy_status_ui")


def on_playback_state_changed(
    owner: Any,
    state: Any,
    *,
    icon_factory: Callable[..., Any] | None = None,
    icon_size_factory: Callable[[int], Any] | None = None,
) -> None:
    playing = _playing_state(state)
    play_btn = getattr(owner, "play_btn", None)
    if play_btn is not None:
        _call(play_btn, "setText", "")
        if icon_factory is None or icon_size_factory is None:
            from app.icons import app_icon, icon_size

            icon_factory = icon_factory or app_icon
            icon_size_factory = icon_size_factory or icon_size
        _call(
            play_btn,
            "setIcon",
            icon_factory("pause" if playing else "play", size=14, color="#D7DAE7"),
        )
        _call(play_btn, "setIconSize", icon_size_factory(14))

    popout = getattr(owner, "_preview_popout", None)
    if popout is not None and hasattr(popout, "set_playing"):
        try:
            popout.set_playing(playing)
        except Exception:
            pass


def _mixer_panel_visible(panel: Any) -> bool:
    visible = getattr(panel, "isVisible", None)
    return bool(visible()) if callable(visible) else False


def _label_text(label: Any) -> str:
    text = getattr(label, "text", None)
    if callable(text):
        return str(text())
    return str(getattr(label, "_text", ""))


def _active_render_track(owner: Any, pos: int) -> Any | None:
    for track in reversed(getattr(owner, "_tracks", []) or []):
        clips = list(getattr(track, "clips", []) or [])
        has_source = getattr(track, "source_path", None) is not None or any(
            getattr(clip, "source_path", None) is not None for clip in clips
        )
        if not has_source:
            continue
        offset = int(getattr(track, "offset_ms", 0) or 0)
        local = pos - offset
        track_duration = int(getattr(track, "duration_ms", 0) or 0)
        if track_duration <= 0 and clips:
            track_duration = max(
                (int(getattr(clip, "timeline_out_ms", 0) or 0) for clip in clips),
                default=0,
            )
        if local < 0 or local >= track_duration:
            continue
        cuts = getattr(track, "cuts", []) or []
        if any(
            int(getattr(cut, "start_ms", 0) or 0) <= local < int(getattr(cut, "end_ms", 0) or 0)
            for cut in cuts
        ):
            continue
        return track
    return None


def _speed_at(owner: Any, track: Any, pos_ms: int) -> float:
    speed_at = getattr(owner, "_speed_at", None)
    if callable(speed_at):
        return float(speed_at(track, pos_ms))
    for seg in getattr(track, "speed_segments", []) or []:
        contains = getattr(seg, "contains", None)
        if callable(contains) and contains(pos_ms):
            return float(getattr(seg, "speed", 1.0))
    return 1.0


def on_position_changed(owner: Any, pos: int) -> None:
    pos = int(pos)
    for row in _values(getattr(owner, "_track_rows", None)):
        _call(row, "set_position", pos)
    for row in _values(getattr(owner, "_audio_rows", None)):
        _call(row, "set_position", pos)
    for row in getattr(owner, "_actor_lane_rows", []) or []:
        _call(row, "set_playhead", pos)
    for row in getattr(owner, "_live2d_lane_rows", []) or []:
        _call(row, "set_playhead", pos)
    for row in getattr(owner, "_ar_pbr_lane_rows", []) or []:
        _call(row, "set_playhead", pos)
    for row in getattr(owner, "_mmd_lane_rows", []) or []:
        _call(row, "set_playhead", pos)
    _call(getattr(owner, "_timeline_ruler", None), "set_playhead", pos)
    _call(owner, "_push_snap_targets_to_rows")
    update_audio_level_meters(owner, pos)

    mixer_panel = getattr(owner, "_audio_mixer_panel", None)
    if mixer_panel is not None and _mixer_panel_visible(mixer_panel):
        mixer_panel.update_levels(pos, getattr(owner, "_audio_tracks", []) or [])
        mixer_panel.update_scopes(pos, getattr(owner, "_audio_tracks", []) or [])

    player = getattr(owner, "_player", None)
    duration = int(player.duration()) if player is not None and hasattr(player, "duration") else 0
    time_label = getattr(owner, "time_label", None)
    if time_label is not None:
        _call(time_label, "setText", f"{_format_ms(pos)} / {_format_ms(duration)}")
    popout = getattr(owner, "_preview_popout", None)
    if popout is not None and hasattr(popout, "set_time_text"):
        try:
            popout.set_time_text(_label_text(time_label))
        except Exception:
            pass
    _call(owner, "_update_subtitle_overlay", pos)
    _call(owner, "_scale_preview_to_fit")
    _call(getattr(owner, "_drawing_canvas", None), "update")
    _call(owner, "_sync_pip_sliders_to_position", pos)
    _call(owner, "_update_bubble_visibility", pos)
    _call(owner, "_update_sticker_visibility", pos)
    _call(owner, "_update_text_clip_overlay", pos)

    active_for_render = _active_render_track(owner, pos)
    if active_for_render is None:
        speed = 1.0
    else:
        local_pos = pos - int(getattr(active_for_render, "offset_ms", 0) or 0)
        speed = _speed_at(owner, active_for_render, local_pos)
    if speed != getattr(owner, "_current_segment_speed", None):
        setattr(owner, "_current_segment_speed", speed)
        try:
            shuttle_rate = float(getattr(owner, "_jkl_transport_rate", 0.0) or 0.0)
        except Exception:
            shuttle_rate = 0.0
        if shuttle_rate > 0.0 and abs(shuttle_rate - 1.0) > 1e-6:
            _call(owner, "_set_transport_speed_label", shuttle_rate)
        else:
            _call(owner, "_set_transport_speed_label", speed)


def _waveform_buckets_per_sec(owner: Any) -> int:
    override = getattr(owner, "_waveform_buckets_per_sec", None)
    if override is not None:
        return int(override)
    try:
        from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC

        return int(WAVEFORM_BUCKETS_PER_SEC)
    except Exception:
        return 40


def update_audio_level_meters(owner: Any, pos_ms: int) -> None:
    buckets_per_sec = _waveform_buckets_per_sec(owner)
    for track in getattr(owner, "_audio_tracks", []) or []:
        row = (getattr(owner, "_audio_rows", None) or {}).get(getattr(track, "id", None))
        if row is None:
            continue
        l_peak = r_peak = 0.0
        for clip in getattr(track, "clips", []) or []:
            if getattr(clip, "source_path", None) is None:
                continue
            local_ms = int(pos_ms) - int(getattr(clip, "offset_ms", 0) or 0)
            if local_ms < 0 or local_ms > int(getattr(clip, "effective_length_ms", 0) or 0):
                continue
            src_ms = int(getattr(clip, "trim_start_ms", 0) or 0) + local_ms
            wf = getattr(clip, "waveform", None)
            if wf is None or getattr(wf, "size", 0) == 0:
                continue
            bucket = int(src_ms / 1000.0 * buckets_per_sec)
            is_stereo = getattr(wf, "ndim", 1) == 2 and wf.shape[0] == 2
            n = wf.shape[1] if is_stereo else len(wf)
            if 0 <= bucket < n:
                volume = float(getattr(track, "volume", 1.0))
                if is_stereo:
                    l_peak = max(l_peak, float(wf[0, bucket]) * volume)
                    r_peak = max(r_peak, float(wf[1, bucket]) * volume)
                else:
                    v = float(wf[bucket]) * volume
                    l_peak = max(l_peak, v)
                    r_peak = max(r_peak, v)
        _call(row, "set_level", l_peak, r_peak)


def on_duration_changed(owner: Any, dur: int) -> None:
    dur = int(dur)
    for row in _values(getattr(owner, "_track_rows", None)):
        _call(row, "_recalc_width")
    _call(getattr(owner, "_timeline_ruler", None), "set_project_duration", dur)
    _call(owner, "_update_tracks_host_width")
    time_label = getattr(owner, "time_label", None)
    if time_label is not None:
        _call(time_label, "setText", f"0:00 / {_format_ms(dur)}")
    _call(getattr(owner, "_subtitle_panel", None), "set_project_duration", dur)
    _call(owner, "_refresh_workbench")


__all__ = [
    "NESTED_AUDIO_PREVIEW_TRACK_ID",
    "VIDEO_EMBEDDED_AUDIO_PREVIEW_TRACK_ID",
    "collect_nested_audio_preview_clips",
    "collect_video_embedded_audio_preview_clips",
    "sync_nested_audio_preview_track",
    "sync_video_embedded_audio_preview_track",
    "sync_ar_pbr_tracks_to_player",
    "sync_mmd_tracks_to_player",
    "sync_actor_tracks_to_player",
    "repaint_timeline_rows",
    "refresh_player_tracks",
    "on_playback_state_changed",
    "on_position_changed",
    "update_audio_level_meters",
    "on_duration_changed",
]
