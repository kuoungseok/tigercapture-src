from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import app.video_editor_thumbnail_controller as thumbs


class FakeSignal:
    def __init__(self) -> None:
        self.slots = []

    def connect(self, slot) -> None:
        self.slots.append(slot)

    def emit(self, *args) -> None:
        for slot in list(self.slots):
            slot(*args)


class FakeExtractor:
    instances = []

    def __init__(self, track_id, source_path, thumb_h, clip_id=-1) -> None:
        self.track_id = track_id
        self.source_path = source_path
        self.thumb_h = thumb_h
        self.clip_id = clip_id
        self.count_determined = FakeSignal()
        self.thumb_ready = FakeSignal()
        self.finished_extracting = FakeSignal()
        self.clip_count_determined = FakeSignal()
        self.clip_thumb_ready = FakeSignal()
        self.finished = FakeSignal()
        self.started = False
        self.stopped = False
        self.deleted = False
        FakeExtractor.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def deleteLater(self) -> None:
        self.deleted = True


class FakeRow:
    def __init__(self) -> None:
        self.updates = 0

    def update(self) -> None:
        self.updates += 1


class FakeOwner:
    def __init__(self, *tracks) -> None:
        self._tracks = list(tracks)
        self._track_rows = {track.id: FakeRow() for track in tracks}
        self._extractors = {}
        self._clip_extractors = {}
        self._retired_thumbnail_extractors = []
        self._sender = None

    def sender(self):
        return self._sender

    def _find_track(self, track_id):
        return next((track for track in self._tracks if track.id == track_id), None)

    def _on_thumb_count(self, track_id, count) -> None:
        thumbs.on_thumb_count(self, track_id, count)

    def _on_thumb_ready(self, track_id, idx, pix) -> None:
        thumbs.on_thumb_ready(self, track_id, idx, pix)

    def _on_extractor_done(self, track_id) -> None:
        thumbs.on_extractor_done(self, track_id)

    def _on_clip_thumb_count(self, track_id, clip_id, count) -> None:
        thumbs.on_clip_thumb_count(self, track_id, clip_id, count)

    def _on_clip_thumb_ready(self, track_id, clip_id, idx, pix) -> None:
        thumbs.on_clip_thumb_ready(self, track_id, clip_id, idx, pix)

    def _on_clip_extractor_done(self, track_id) -> None:
        thumbs.on_clip_extractor_done(self, track_id)


def test_stale_sender_is_ignored_for_thumb_count(tmp_path, monkeypatch):
    track = SimpleNamespace(
        id=7,
        source_path=tmp_path / "clip.mp4",
        thumbnails=["keep"],
        clips=[],
    )
    owner = FakeOwner(track)
    owner._extractors[track.id] = FakeExtractor(track.id, track.source_path, 48)
    owner._sender = FakeExtractor(track.id, track.source_path, 48)
    prepare_calls = []
    monkeypatch.setattr(
        thumbs,
        "prepare_timeline_thumb_cache",
        lambda *args: prepare_calls.append(args),
    )

    thumbs.on_thumb_count(owner, track.id, 3)

    assert track.thumbnails == ["keep"]
    assert prepare_calls == []
    assert owner._track_rows[track.id].updates == 0


def test_thumb_count_prepares_slots_cache_and_row(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    track = SimpleNamespace(id=3, source_path=source, thumbnails=[], clips=[])
    owner = FakeOwner(track)
    extractor = FakeExtractor(track.id, source, 48)
    owner._extractors[track.id] = extractor
    owner._sender = extractor
    prepare_calls = []
    monkeypatch.setattr(
        thumbs,
        "prepare_timeline_thumb_cache",
        lambda *args: prepare_calls.append(args),
    )

    thumbs.on_thumb_count(owner, track.id, 4)

    assert track.thumbnails == [None, None, None, None]
    assert prepare_calls == [(source, 4, thumbs.THUMB_H)]
    assert owner._track_rows[track.id].updates == 1


def test_thumb_ready_stores_pixmap_cache_and_updates_row(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    track = SimpleNamespace(id=11, source_path=source, thumbnails=[None, None], clips=[])
    owner = FakeOwner(track)
    extractor = FakeExtractor(track.id, source, 48)
    owner._extractors[track.id] = extractor
    owner._sender = extractor
    pixmap = object()
    store_calls = []
    monkeypatch.setattr(
        thumbs,
        "store_timeline_thumb_cache",
        lambda *args: store_calls.append(args),
    )

    thumbs.on_thumb_ready(owner, track.id, 1, pixmap)

    assert track.thumbnails == [None, pixmap]
    assert store_calls == [(source, 1, pixmap, thumbs.THUMB_H)]
    assert owner._track_rows[track.id].updates == 1


def test_retired_extractor_stops_and_cleans_up_after_finished(tmp_path):
    track = SimpleNamespace(id=5, source_path=tmp_path / "clip.mp4", thumbnails=[])
    owner = FakeOwner(track)
    extractor = FakeExtractor(track.id, track.source_path, 48)

    thumbs.retire_thumbnail_extractor(owner, extractor)

    assert extractor.stopped is True
    assert extractor in owner._retired_thumbnail_extractors

    extractor.finished.emit()

    assert extractor not in owner._retired_thumbnail_extractors
    assert extractor.deleted is True


def test_extractor_done_pops_current_sender_and_deletes(tmp_path):
    track = SimpleNamespace(id=13, source_path=tmp_path / "clip.mp4", thumbnails=[])
    owner = FakeOwner(track)
    extractor = FakeExtractor(track.id, track.source_path, 48)
    owner._extractors[track.id] = extractor
    owner._sender = extractor

    thumbs.on_extractor_done(owner, track.id)

    assert track.id not in owner._extractors
    assert extractor.deleted is True


def test_clip_thumb_ready_updates_matching_clip_only(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    clip = SimpleNamespace(id=22, source_path=source, thumbnails=[None, None])
    track = SimpleNamespace(id=2, source_path=None, thumbnails=[], clips=[clip])
    owner = FakeOwner(track)
    extractor = FakeExtractor(track.id, source, 48, clip_id=clip.id)
    owner._clip_extractors[(track.id, clip.id)] = extractor
    owner._sender = extractor
    pixmap = object()
    store_calls = []
    monkeypatch.setattr(
        thumbs,
        "store_timeline_thumb_cache",
        lambda *args: store_calls.append(args),
    )

    thumbs.on_clip_thumb_ready(owner, track.id, clip.id, 0, pixmap)

    assert clip.thumbnails == [pixmap, None]
    assert store_calls == [(source, 0, pixmap, thumbs.THUMB_H)]
    assert owner._track_rows[track.id].updates == 1


def test_start_thumbnail_extraction_connects_owner_wrappers(tmp_path, monkeypatch):
    FakeExtractor.instances = []
    source = tmp_path / "clip.mp4"
    track = SimpleNamespace(id=31, source_path=source, thumbnails=[], clips=[])
    owner = FakeOwner(track)
    monkeypatch.setattr(thumbs, "load_timeline_thumb_cache", lambda *args: None)
    monkeypatch.setattr(thumbs, "ThumbnailExtractor", FakeExtractor)

    thumbs.start_thumbnail_extraction(owner, track)

    extractor = FakeExtractor.instances[-1]
    assert owner._extractors[track.id] is extractor
    assert extractor.started is True
    assert extractor.count_determined.slots == [owner._on_thumb_count]
    assert extractor.thumb_ready.slots == [owner._on_thumb_ready]
    assert extractor.finished_extracting.slots == [owner._on_extractor_done]


def test_start_thumbnail_extraction_for_image_sets_thumb_without_extractor(tmp_path, monkeypatch):
    FakeExtractor.instances = []
    source = tmp_path / "poster.png"
    track = SimpleNamespace(id=41, source_path=source, thumbnails=[], clips=[])
    owner = FakeOwner(track)
    monkeypatch.setattr(thumbs, "ThumbnailExtractor", FakeExtractor)
    monkeypatch.setattr(thumbs, "image_timeline_thumbnails", lambda *args: ["image-thumb"])

    thumbs.start_thumbnail_extraction(owner, track)

    assert track.thumbnails == ["image-thumb"]
    assert FakeExtractor.instances == []
    assert owner._track_rows[track.id].updates == 1


def test_start_clip_thumbnail_extraction_for_image_sets_thumb_without_extractor(tmp_path, monkeypatch):
    FakeExtractor.instances = []
    source = tmp_path / "poster.jpg"
    clip = SimpleNamespace(id=8, source_path=source, thumbnails=[])
    track = SimpleNamespace(id=42, source_path=None, thumbnails=[], clips=[clip])
    owner = FakeOwner(track)
    monkeypatch.setattr(thumbs, "ThumbnailExtractor", FakeExtractor)
    monkeypatch.setattr(thumbs, "image_timeline_thumbnails", lambda *args: ["clip-image-thumb"])

    thumbs.start_thumbnail_extraction_for_clip(owner, clip, track.id)

    assert clip.thumbnails == ["clip-image-thumb"]
    assert FakeExtractor.instances == []
    assert owner._track_rows[track.id].updates == 1
