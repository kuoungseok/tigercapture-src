from __future__ import annotations

from typing import Any, MutableMapping

from PySide6.QtGui import QImage, QPixmap

from app.timeline_thumbnail_cache import (
    load_timeline_thumb_cache,
    prepare_timeline_thumb_cache,
    store_timeline_thumb_cache,
)
from app.video_editor_thumbnailing import THUMB_H, ThumbnailExtractor
from app.image_media import image_timeline_thumbnails, is_image_path


def _track_extractors(owner: Any) -> MutableMapping[int, Any]:
    extractors = getattr(owner, "_extractors", None)
    if extractors is None:
        extractors = {}
        setattr(owner, "_extractors", extractors)
    return extractors


def _clip_extractors(owner: Any) -> MutableMapping[tuple[int, int], Any]:
    extractors = getattr(owner, "_clip_extractors", None)
    if extractors is None:
        extractors = {}
        setattr(owner, "_clip_extractors", extractors)
    return extractors


def _retired_extractors(owner: Any) -> list[Any]:
    retired = getattr(owner, "_retired_thumbnail_extractors", None)
    if retired is None:
        retired = []
        setattr(owner, "_retired_thumbnail_extractors", retired)
    return retired


def _owner_sender(owner: Any) -> Any:
    sender = getattr(owner, "sender", None)
    if callable(sender):
        return sender()
    return None


def _find_track(owner: Any, track_id: int) -> Any | None:
    finder = getattr(owner, "_find_track", None)
    if callable(finder):
        return finder(track_id)
    for track in getattr(owner, "_tracks", []) or []:
        if getattr(track, "id", None) == track_id:
            return track
    return None


def _find_clip(track: Any, clip_id: int) -> Any | None:
    for clip in getattr(track, "clips", []) or []:
        if getattr(clip, "id", None) == clip_id:
            return clip
    return None


def _update_track_row(owner: Any, track_id: int) -> None:
    rows = getattr(owner, "_track_rows", None) or {}
    row = rows.get(track_id)
    updater = getattr(row, "update", None)
    if callable(updater):
        updater()


def sender_is_current_track_extractor(owner: Any, track_id: int) -> bool:
    return _owner_sender(owner) is _track_extractors(owner).get(track_id)


def sender_is_current_clip_extractor(
    owner: Any, track_id: int, clip_id: int
) -> bool:
    return _owner_sender(owner) is _clip_extractors(owner).get((track_id, clip_id))


def _connect_owner_slot(extractor: Any, signal_name: str, owner: Any, slot_name: str) -> None:
    signal = getattr(extractor, signal_name, None)
    connect = getattr(signal, "connect", None)
    slot = getattr(owner, slot_name, None)
    if callable(connect) and callable(slot):
        connect(slot)


def retire_thumbnail_extractor(owner: Any, ex: Any | None) -> None:
    if ex is None:
        return
    retired = _retired_extractors(owner)
    retired.append(ex)

    def _cleanup() -> None:
        try:
            retired.remove(ex)
        except ValueError:
            pass
        delete_later = getattr(ex, "deleteLater", None)
        if callable(delete_later):
            delete_later()

    finished = getattr(ex, "finished", None)
    connect = getattr(finished, "connect", None)
    if callable(connect):
        connect(_cleanup)
    stopper = getattr(ex, "stop", None)
    if callable(stopper):
        stopper()


def start_thumbnail_extraction(owner: Any, track: Any) -> None:
    source_path = getattr(track, "source_path", None)
    if source_path is None:
        return
    track_id = int(getattr(track, "id"))
    if is_image_path(source_path):
        track.thumbnails = image_timeline_thumbnails(source_path, THUMB_H)
        _update_track_row(owner, track_id)
        return
    cached = load_timeline_thumb_cache(source_path, THUMB_H)
    extractors = _track_extractors(owner)
    if cached:
        prev = extractors.pop(track_id, None)
        retire_thumbnail_extractor(owner, prev)
        track.thumbnails = cached
        _update_track_row(owner, track_id)
        return

    prev = extractors.pop(track_id, None)
    retire_thumbnail_extractor(owner, prev)
    ex = ThumbnailExtractor(track_id, source_path, THUMB_H)
    _connect_owner_slot(ex, "count_determined", owner, "_on_thumb_count")
    _connect_owner_slot(ex, "thumb_ready", owner, "_on_thumb_ready")
    _connect_owner_slot(ex, "finished_extracting", owner, "_on_extractor_done")
    track.thumbnails = []
    extractors[track_id] = ex
    ex.start()


def on_thumb_count(owner: Any, track_id: int, count: int) -> None:
    if not sender_is_current_track_extractor(owner, track_id):
        return
    track = _find_track(owner, track_id)
    if track is None:
        return
    count = max(0, int(count))
    track.thumbnails = [None] * count
    source_path = getattr(track, "source_path", None)
    if source_path is not None:
        prepare_timeline_thumb_cache(source_path, count, THUMB_H)
    _update_track_row(owner, track_id)


def on_thumb_ready(owner: Any, track_id: int, idx: int, pix: Any) -> None:
    if not sender_is_current_track_extractor(owner, track_id):
        return
    track = _find_track(owner, track_id)
    if track is None:
        return
    thumbnails = getattr(track, "thumbnails", [])
    if idx < 0 or idx >= len(thumbnails):
        return
    source_path = getattr(track, "source_path", None)
    if isinstance(pix, QImage):
        if source_path is not None:
            store_timeline_thumb_cache(source_path, idx, pix, THUMB_H)
        pix = QPixmap.fromImage(pix)
    elif source_path is not None:
        store_timeline_thumb_cache(source_path, idx, pix, THUMB_H)
    track.thumbnails[idx] = pix
    _update_track_row(owner, track_id)


def on_extractor_done(owner: Any, track_id: int) -> None:
    sender = _owner_sender(owner)
    extractors = _track_extractors(owner)
    if sender is not extractors.get(track_id):
        return
    ex = extractors.pop(track_id, None)
    if ex is not None:
        delete_later = getattr(ex, "deleteLater", None)
        if callable(delete_later):
            delete_later()


def start_thumbnail_extraction_for_clip(owner: Any, clip: Any, track_id: int) -> None:
    source_path = getattr(clip, "source_path", None)
    if source_path is None:
        return
    if is_image_path(source_path):
        clip.thumbnails = image_timeline_thumbnails(source_path, THUMB_H)
        _update_track_row(owner, track_id)
        return
    cached = load_timeline_thumb_cache(source_path, THUMB_H)
    if cached:
        clip.thumbnails = cached
        _update_track_row(owner, track_id)
        return

    clip_id = int(getattr(clip, "id", -1))
    key = (track_id, clip_id)
    extractors = _clip_extractors(owner)
    prev = extractors.pop(key, None)
    retire_thumbnail_extractor(owner, prev)
    clip.thumbnails = []
    ex = ThumbnailExtractor(track_id, source_path, THUMB_H, clip_id=clip_id)
    _connect_owner_slot(ex, "clip_count_determined", owner, "_on_clip_thumb_count")
    _connect_owner_slot(ex, "clip_thumb_ready", owner, "_on_clip_thumb_ready")
    _connect_owner_slot(ex, "finished_extracting", owner, "_on_clip_extractor_done")
    extractors[key] = ex
    ex.start()


def on_clip_thumb_count(owner: Any, track_id: int, clip_id: int, count: int) -> None:
    if not sender_is_current_clip_extractor(owner, track_id, clip_id):
        return
    track = _find_track(owner, track_id)
    if track is None:
        return
    clip = _find_clip(track, clip_id)
    if clip is None:
        return
    count = max(0, int(count))
    clip.thumbnails = [None] * count
    source_path = getattr(clip, "source_path", None)
    if source_path is not None:
        prepare_timeline_thumb_cache(source_path, count, THUMB_H)
    _update_track_row(owner, track_id)


def on_clip_thumb_ready(
    owner: Any, track_id: int, clip_id: int, idx: int, pix: Any
) -> None:
    if not sender_is_current_clip_extractor(owner, track_id, clip_id):
        return
    track = _find_track(owner, track_id)
    if track is None:
        return
    clip = _find_clip(track, clip_id)
    if clip is None:
        return
    thumbnails = getattr(clip, "thumbnails", [])
    if idx < 0 or idx >= len(thumbnails):
        return
    source_path = getattr(clip, "source_path", None)
    if isinstance(pix, QImage):
        if source_path is not None:
            store_timeline_thumb_cache(source_path, idx, pix, THUMB_H)
        pix = QPixmap.fromImage(pix)
    elif source_path is not None:
        store_timeline_thumb_cache(source_path, idx, pix, THUMB_H)
    clip.thumbnails[idx] = pix
    _update_track_row(owner, track_id)


def on_clip_extractor_done(owner: Any, track_id: int) -> None:
    sender = _owner_sender(owner)
    extractors = _clip_extractors(owner)
    for key in list(extractors.keys()):
        if key[0] == track_id and extractors.get(key) is sender:
            ex = extractors.pop(key, None)
            if ex is not None:
                delete_later = getattr(ex, "deleteLater", None)
                if callable(delete_later):
                    delete_later()
            break


__all__ = [
    "retire_thumbnail_extractor",
    "start_thumbnail_extraction",
    "on_thumb_count",
    "on_thumb_ready",
    "on_extractor_done",
    "start_thumbnail_extraction_for_clip",
    "on_clip_thumb_count",
    "on_clip_thumb_ready",
    "on_clip_extractor_done",
    "sender_is_current_track_extractor",
    "sender_is_current_clip_extractor",
]
