from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


class _FakeMime:
    pass


class _FakeMediaPool:
    def __init__(self) -> None:
        self.added: list[Path] = []
        self.performance_flags: list[tuple[Path, bool]] = []

    def add_path(self, path: Path) -> bool:
        self.added.append(Path(path))
        return True

    def set_performance_source_path(self, path: Path, enabled: bool) -> None:
        self.performance_flags.append((Path(path), bool(enabled)))


class _RoutingOwner:
    def __init__(self, *, vrm=(), mmd=(), ar=(), perf=(), media=()) -> None:
        self.vrm = tuple(Path(p) for p in vrm)
        self.mmd = tuple(Path(p) for p in mmd)
        self.ar = tuple(Path(p) for p in ar)
        self.perf = tuple(Path(p) for p in perf)
        self.media = tuple(Path(p) for p in media)

    def _vrm_avatar_paths_from_mime(self, _mime):
        return list(self.vrm)

    def _mmd_paths_from_mime(self, _mime):
        return list(self.mmd)

    def _ar_pbr_paths_from_mime(self, _mime):
        return list(self.ar)

    def _performance_source_paths_from_mime(self, _mime):
        return list(self.perf)

    def _timeline_media_paths_from_mime(self, _mime):
        return list(self.media)


def test_route_window_prefers_special_assets_before_plain_media(tmp_path):
    from app.video_editor_media_import_controller import (
        ROUTE_VRM_AVATAR,
        TARGET_WINDOW,
        route_mime_drop,
    )

    video = tmp_path / "plain.mp4"
    audio = tmp_path / "voice.wav"
    owner = _RoutingOwner(
        vrm=(tmp_path / "avatar.vrm",),
        mmd=(tmp_path / "actor.pmx",),
        ar=(tmp_path / "prop.glb",),
        perf=(video,),
        media=(video, audio),
    )

    decision = route_mime_drop(owner, _FakeMime(), target=TARGET_WINDOW)

    assert decision.route == ROUTE_VRM_AVATAR
    assert decision.path == tmp_path / "avatar.vrm"


def test_tracks_host_route_preserves_mmd_perf_ar_media_order(tmp_path):
    from app.video_editor_media_import_controller import (
        ROUTE_AR_PBR,
        ROUTE_MMD,
        ROUTE_PERFORMANCE_SOURCE,
        TARGET_TRACKS_HOST,
        route_mime_drop,
        route_tracks_host_drop,
    )

    video = tmp_path / "face.mp4"
    owner = _RoutingOwner(
        mmd=(tmp_path / "actor.pmx",),
        ar=(tmp_path / "prop.glb",),
        perf=(video,),
        media=(video,),
    )
    owner._px_per_sec = 100.0
    owner._timeline_content_margin = lambda: 180

    decision = route_tracks_host_drop(owner, _FakeMime(), drop_x=430.0)

    assert decision.route == ROUTE_MMD
    assert decision.start_ms == 2500

    owner.mmd = ()
    assert route_mime_drop(owner, _FakeMime(), target=TARGET_TRACKS_HOST).route == ROUTE_PERFORMANCE_SOURCE

    owner.perf = ()
    assert route_mime_drop(owner, _FakeMime(), target=TARGET_TRACKS_HOST).route == ROUTE_AR_PBR


def test_video_row_route_prefers_ar_then_performance_then_media(tmp_path):
    from app.video_editor_media_import_controller import (
        ROUTE_AR_PBR,
        ROUTE_PERFORMANCE_SOURCE,
        ROUTE_VIDEO,
        route_video_row_drop,
    )

    video = tmp_path / "face_input.mp4"
    owner = _RoutingOwner(
        ar=(tmp_path / "prop.fbx",),
        perf=(video,),
        media=(video,),
    )

    assert route_video_row_drop(owner, 7, _FakeMime()).route == ROUTE_AR_PBR

    owner.ar = ()
    assert route_video_row_drop(owner, 7, _FakeMime()).route == ROUTE_PERFORMANCE_SOURCE

    owner.perf = ()
    assert route_video_row_drop(owner, 7, _FakeMime()).route == ROUTE_VIDEO


def test_audio_row_route_keeps_special_assets_before_video_audio(tmp_path):
    from app.video_editor_media_import_controller import (
        ROUTE_MMD,
        ROUTE_PERFORMANCE_SOURCE,
        ROUTE_VIDEO,
        route_audio_row_drop,
    )

    video = tmp_path / "face_input.mp4"
    owner = _RoutingOwner(
        mmd=(tmp_path / "motion.vmd",),
        perf=(video,),
        media=(video, tmp_path / "dialogue.wav"),
    )

    assert route_audio_row_drop(owner, 11, _FakeMime()).route == ROUTE_MMD

    owner.mmd = ()
    assert route_audio_row_drop(owner, 11, _FakeMime()).route == ROUTE_PERFORMANCE_SOURCE

    owner.perf = ()
    assert route_audio_row_drop(owner, 11, _FakeMime()).route == ROUTE_VIDEO


def test_add_timeline_media_dispatches_performance_source_before_video(tmp_path, monkeypatch):
    from app.timeline_model import VideoClip
    from app.video_editor_media_import_controller import add_timeline_media_from_mime
    from app.video_track_legacy import VideoTrack

    video = tmp_path / "face_input.mp4"
    owner = _RoutingOwner(perf=(video,), media=(video,))
    owner._tracks = []
    owner._audio_tracks = []
    owner._next_track_id = 20
    owner._next_video_clip_id = 200
    owner._player = SimpleNamespace(position=lambda: 1234)
    owner._media_pool = _FakeMediaPool()

    monkeypatch.setattr(
        "app.video_editor_media_import_controller.probe_video_duration_ms",
        lambda _path: 3000,
    )

    assert add_timeline_media_from_mime(owner, _FakeMime()) is True

    assert len(owner._tracks) == 1
    track = owner._tracks[0]
    assert isinstance(track, VideoTrack)
    assert getattr(track, "performance_source") is True
    assert track.source_path is None
    assert len(track.clips) == 1
    assert isinstance(track.clips[0], VideoClip)
    assert getattr(track.clips[0], "performance_source") is True
    assert track.clips[0].source_path == video
    assert track.clips[0].timeline_in_ms == 1234
    assert owner._media_pool.added == [video]
    assert owner._media_pool.performance_flags == [(video, True)]


def test_append_clip_to_track_uses_video_clip_tail_position(tmp_path, monkeypatch):
    from app.timeline_model import VideoClip
    from app.video_editor_media_import_controller import append_clip_to_track
    from app.video_track_legacy import VideoTrack

    first = VideoClip(
        id=1,
        source_path=tmp_path / "first.mp4",
        source_duration_ms=1000,
        timeline_in_ms=250,
        source_in_ms=0,
        source_out_ms=1000,
    )
    track = VideoTrack(id=5, clips=[first], clips_explicit=True)
    owner = SimpleNamespace(_tracks=[track], _next_video_clip_id=50)
    second = tmp_path / "second.mp4"

    monkeypatch.setattr(
        "app.video_editor_media_import_controller.probe_video_duration_ms",
        lambda _path: 2200,
    )

    clip = append_clip_to_track(owner, track, second)

    assert isinstance(clip, VideoClip)
    assert clip.id == 50
    assert clip.source_path == second
    assert clip.source_duration_ms == 2200
    assert clip.timeline_in_ms == first.timeline_out_ms
    assert track.clips == [first, clip]


def test_add_timeline_media_dispatches_image_track(tmp_path):
    from app.timeline_model import VideoClip
    from app.video_editor_media_import_controller import add_timeline_media_from_mime
    from app.video_track_legacy import VideoTrack

    image = tmp_path / "poster.png"
    owner = _RoutingOwner(media=(image,))
    owner._tracks = []
    owner._audio_tracks = []
    owner._next_track_id = 9
    owner._next_video_clip_id = 90
    owner._player = SimpleNamespace(position=lambda: 1500)
    owner._media_pool = _FakeMediaPool()

    assert add_timeline_media_from_mime(owner, _FakeMime()) is True

    assert len(owner._tracks) == 1
    track = owner._tracks[0]
    assert isinstance(track, VideoTrack)
    assert track.source_path is None
    assert getattr(track, "track_type") == "image"
    assert len(track.clips) == 1
    clip = track.clips[0]
    assert isinstance(clip, VideoClip)
    assert clip.source_path == image
    assert getattr(clip, "track_type") == "image"
    assert clip.timeline_in_ms == 1500
    assert clip.source_duration_ms == 5000


def test_append_image_clip_uses_tail_and_marks_track(tmp_path):
    from app.timeline_model import VideoClip
    from app.video_editor_media_import_controller import append_image_clip_to_track
    from app.video_track_legacy import VideoTrack

    first = VideoClip(
        id=1,
        source_path=tmp_path / "first.png",
        source_duration_ms=3000,
        timeline_in_ms=250,
        source_in_ms=0,
        source_out_ms=3000,
    )
    first.track_type = "image"
    track = VideoTrack(id=5, source_path=None, clips=[first], clips_explicit=True)
    track.track_type = "image"
    owner = SimpleNamespace(_tracks=[track], _next_video_clip_id=50)
    second = tmp_path / "second.jpg"

    clip = append_image_clip_to_track(owner, track, second, duration_ms=1800)

    assert isinstance(clip, VideoClip)
    assert clip.id == 50
    assert clip.source_path == second
    assert clip.source_duration_ms == 1800
    assert clip.timeline_in_ms == first.timeline_out_ms
    assert getattr(track, "track_type") == "image"
    assert getattr(clip, "track_type") == "image"
