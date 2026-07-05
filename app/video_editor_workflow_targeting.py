from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

ClipPair = tuple[Any | None, Any | None]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _try_call(func: Any, *args: Any, **kwargs: Any) -> Any:
    if not callable(func):
        return None
    try:
        return func(*args, **kwargs)
    except Exception:
        return None


def _call_succeeded(func: Any, *args: Any, **kwargs: Any) -> bool:
    if not callable(func):
        return False
    try:
        func(*args, **kwargs)
    except Exception:
        return False
    return True


def _iter_tracks(owner: Any) -> Iterable[Any]:
    for name in ("workflow_tracks", "iter_workflow_tracks"):
        provider = getattr(owner, name, None)
        if callable(provider):
            tracks = _try_call(provider)
            if tracks is not None:
                return tracks
    for name in ("tracks", "_tracks"):
        tracks = getattr(owner, name, None)
        if tracks is not None:
            return tracks
    return ()


def _track_id(track: Any, default: int = -1) -> int:
    return _safe_int(getattr(track, "id", default), default)


def _clip_id(clip: Any, default: int = -1) -> int:
    return _safe_int(getattr(clip, "id", default), default)


def _clip_span(clip: Any) -> tuple[int, int]:
    start = _safe_int(getattr(clip, "timeline_in_ms", 0), 0)
    end = _safe_int(getattr(clip, "timeline_out_ms", start), start)
    return start, end


def _clip_at_ms(track: Any, ms: int) -> Any | None:
    for clip in getattr(track, "clips", []) or []:
        start, end = _clip_span(clip)
        if start <= ms < end:
            return clip
    return None


def _find_track(owner: Any, track_id: int) -> Any | None:
    for name in ("find_workflow_track", "_find_track"):
        finder = getattr(owner, name, None)
        if callable(finder):
            track = _try_call(finder, int(track_id))
            if track is not None:
                return track
    for track in _iter_tracks(owner) or []:
        if _track_id(track) == int(track_id):
            return track
    return None


def _active_track(owner: Any) -> Any | None:
    for name in ("workflow_active_track", "active_track", "_active_track"):
        provider = getattr(owner, name, None)
        if callable(provider):
            track = _try_call(provider)
            if track is not None:
                return track
    active_track = getattr(owner, "active_track", None)
    if active_track is not None and not callable(active_track):
        return active_track
    active_track_id = getattr(owner, "active_track_id", getattr(owner, "_active_track_id", None))
    if active_track_id is not None:
        return _find_track(owner, _safe_int(active_track_id, -1))
    return None


def _player(owner: Any) -> Any | None:
    return getattr(owner, "player", getattr(owner, "_player", None))


def _player_position(owner: Any) -> int:
    player = _player(owner)
    if player is None:
        return 0
    for name in ("position", "get_position", "pos"):
        getter = getattr(player, name, None)
        if callable(getter):
            return _safe_int(_try_call(getter), 0)
    return _safe_int(getattr(player, "position_ms", 0), 0)


def _selected_pairs(owner: Any) -> list[tuple[int, int]]:
    for name in ("workflow_selected_clips", "selected_clip_ids"):
        provider = getattr(owner, name, None)
        if callable(provider):
            raw_pairs = _try_call(provider)
            if raw_pairs is not None:
                return [(_safe_int(track_id), _safe_int(clip_id)) for track_id, clip_id in raw_pairs]
    raw_pairs = getattr(owner, "selected_clip_ids", getattr(owner, "selected_clips", getattr(owner, "_selected_clips", [])))
    pairs: list[tuple[int, int]] = []
    for raw in raw_pairs or []:
        try:
            track_id, clip_id = raw
        except Exception:
            continue
        pairs.append((_safe_int(track_id), _safe_int(clip_id)))
    return pairs


def first_video_clip_candidate(owner: Any) -> ClipPair:
    for track in _iter_tracks(owner) or []:
        clips = list(getattr(track, "clips", []) or [])
        if clips:
            return track, clips[0]
    return None, None


def select_workflow_video_clip(owner: Any, track: Any, clip: Any) -> bool:
    if track is None or clip is None:
        return False
    try:
        track_id = int(getattr(track, "id"))
        clip_id = int(getattr(clip, "id"))
    except Exception:
        return False

    setter = getattr(owner, "set_workflow_clip_selection", None)
    if callable(setter):
        selected = _try_call(setter, track_id, clip_id)
        if selected is False:
            return False
    else:
        try:
            setattr(owner, "_active_track_id", track_id)
            setattr(owner, "_selected_clips", [(track_id, clip_id)])
        except Exception:
            return False

    _try_call(getattr(owner, "_broadcast_clip_selection", None))

    row = None
    row_for_track = getattr(owner, "workflow_track_row", None)
    if callable(row_for_track):
        row = _try_call(row_for_track, track_id)
    if row is None:
        rows = getattr(owner, "track_rows", getattr(owner, "_track_rows", {})) or {}
        getter = getattr(rows, "get", None)
        row = getter(track_id) if callable(getter) else None
    if row is not None:
        _try_call(getattr(row, "set_selected_clip_ids", None), {clip_id})
        _try_call(getattr(row, "flash_timeline_burst", None), "select", _safe_int(getattr(clip, "timeline_in_ms", 0), 0))
        _try_call(getattr(row, "update", None))

    _try_call(getattr(owner, "_refresh_workbench", None))
    return True


def first_media_pool_path(owner: Any, predicate: Callable[[Path], bool]) -> Path | None:
    item_provider = getattr(owner, "media_pool_items", None)
    if callable(item_provider):
        raw_paths = _try_call(item_provider) or []
    else:
        pool = getattr(owner, "media_pool", getattr(owner, "_media_pool", None))
        items = getattr(pool, "items", None) if pool is not None else None
        raw_paths = _try_call(items) if callable(items) else []

    for raw in raw_paths or []:
        try:
            path = Path(raw)
        except Exception:
            continue
        try:
            if predicate(path):
                return path
        except Exception:
            continue
    return None


def _is_live2d_path(path: Path) -> bool:
    try:
        from app.live2d.compat import is_live2d_candidate

        return path.is_file() and is_live2d_candidate(str(path))
    except Exception:
        return path.is_file() and path.name.casefold().endswith(".model3.json")


def _is_spine_path(path: Path) -> bool:
    try:
        from app.spine_editor.actor_lane_row import _is_spine_candidate

        return path.is_file() and _is_spine_candidate(str(path))
    except Exception:
        return path.is_file() and path.suffix.casefold() in {".json", ".skel", ".atlas"}


def actor_model_candidate(owner: Any, actor_kind: str) -> str:
    kind = str(actor_kind or "").casefold()
    if kind == "live2d":
        candidate = first_media_pool_path(owner, _is_live2d_path)
        return str(candidate) if candidate is not None else ""
    if kind == "spine":
        candidate = first_media_pool_path(owner, _is_spine_path)
        return str(candidate) if candidate is not None else ""
    return ""


def selected_video_clip(owner: Any) -> ClipPair:
    pairs = _selected_pairs(owner)
    if not pairs:
        return None, None
    track_id, clip_id = pairs[0]
    track = _find_track(owner, track_id)
    if track is None:
        return None, None
    clip = next((candidate for candidate in getattr(track, "clips", []) or [] if _clip_id(candidate) == int(clip_id)), None)
    return track, clip


def _selected_video_clip_from_owner(owner: Any) -> ClipPair:
    provider = getattr(owner, "_selected_video_clip", None)
    if callable(provider):
        pair = _try_call(provider)
        if pair is not None:
            try:
                track, clip = pair
                return track, clip
            except Exception:
                pass
    return selected_video_clip(owner)


def workflow_target_video_clip(owner: Any) -> ClipPair:
    target_mode = str(getattr(owner, "_workflow_target_mode", "auto") or "auto")
    if target_mode == "selected_clip":
        return _selected_video_clip_from_owner(owner)
    if target_mode in {"audio", "color"}:
        return None, None

    forced_track_id = getattr(owner, "_workflow_forced_track_id", None)
    if forced_track_id is not None:
        track = _find_track(owner, _safe_int(forced_track_id, -1))
        if track is None:
            return None, None
        pos = getattr(owner, "_workflow_forced_ms", None)
        if pos is None:
            pos = _player_position(owner)
        clip = _clip_at_ms(track, _safe_int(pos, 0))
        return track, clip

    if target_mode != "active_track":
        track, clip = _selected_video_clip_from_owner(owner)
        if track is not None and clip is not None:
            return track, clip

    track = _active_track(owner)
    if track is None:
        return None, None
    pos = _player_position(owner)
    clip = _clip_at_ms(track, pos)
    if clip is not None:
        return track, clip
    clips = list(getattr(track, "clips", []) or [])
    return (track, clips[0]) if clips else (track, None)


def workflow_start_ms(owner: Any, track: Any = None, clip: Any = None, explicit_ms: Any = None) -> int:
    if explicit_ms is not None:
        explicit = _int_or_none(explicit_ms)
        if explicit is not None:
            return max(0, explicit)
    if clip is not None:
        return max(0, _safe_int(getattr(clip, "timeline_in_ms", 0), 0))
    pos = _player_position(owner)
    if track is not None and _safe_int(getattr(track, "duration_ms", 0), 0) > 0:
        return max(0, min(int(pos), _safe_int(getattr(track, "duration_ms", 0), 0)))
    return max(0, int(pos))


def focus_preview_at_workflow_ms(owner: Any, ms: Any, *, track: Any = None) -> None:
    try:
        target = max(0, int(ms))
    except Exception:
        return

    try:
        setattr(owner, "_last_workflow_focus_ms", int(target))
    except Exception:
        pass
    if track is not None:
        try:
            setattr(owner, "_last_workflow_focus_track_id", int(getattr(track, "id")))
        except Exception:
            pass
        try:
            track_id = int(getattr(track, "id", -1))
            active_track_id = int(getattr(owner, "_active_track_id", -1))
            if track_id != active_track_id:
                _try_call(getattr(owner, "_set_active_track", None), track_id)
        except Exception:
            pass

    player = _player(owner)
    if player is not None:
        if not _call_succeeded(getattr(player, "set_position", None), target):
            _call_succeeded(getattr(player, "setPosition", None), target)

    refresh = getattr(owner, "_refresh_preview_soft", None)
    if callable(refresh):
        _call_succeeded(refresh, track)

    _try_call(getattr(owner, "_ensure_playhead_visible", None))


__all__ = [
    "actor_model_candidate",
    "first_media_pool_path",
    "first_video_clip_candidate",
    "focus_preview_at_workflow_ms",
    "select_workflow_video_clip",
    "selected_video_clip",
    "workflow_start_ms",
    "workflow_target_video_clip",
]
