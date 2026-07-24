from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.simple_video_player import PlayerState
from app import video_editor_player_bridge as bridge


class _FakeAudioTrack:
    def __init__(self, *, id, clips, label="") -> None:
        self.id = id
        self.clips = list(clips)
        self.label = label

    def extent_ms(self) -> int:
        return max(
            (
                int(getattr(clip, "offset_ms", 0))
                + int(getattr(clip, "effective_length_ms", 0))
                for clip in self.clips
            ),
            default=0,
        )


class _Mixer:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.updated = None

    def update_track(self, track) -> None:
        self.updated = track
        self.log.append(f"mixer.update:{track.id}:{track.label}")

    def remove_track(self, track_id: int) -> None:
        self.log.append(f"mixer.remove:{track_id}")


class _Row:
    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    def update(self) -> None:
        self.log.append(f"{self.name}.update")

    def set_position(self, pos: int) -> None:
        self.log.append(f"{self.name}.set_position:{pos}")

    def set_playhead(self, pos: int) -> None:
        self.log.append(f"{self.name}.set_playhead:{pos}")

    def _recalc_width(self) -> None:
        self.log.append(f"{self.name}.recalc")

    def set_level(self, left: float, right: float) -> None:
        self.log.append(f"{self.name}.level:{left:.2f}:{right:.2f}")


class _Label:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self._text = ""

    def setText(self, text: str) -> None:
        self._text = text
        self.log.append(f"label.text:{text}")

    def text(self) -> str:
        return self._text


def _audio_clip(**kwargs):
    defaults = {
        "id": 1,
        "source_path": "voice.wav",
        "offset_ms": 0,
        "effective_length_ms": 100,
        "trim_start_ms": 0,
        "waveform": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_collect_nested_audio_preview_clips_flattens_offsets_and_ids() -> None:
    nested_audio = _audio_clip(id=10, offset_ms=7, effective_length_ms=50)
    child_audio = _audio_clip(id=20, offset_ms=11, effective_length_ms=60)
    child_clip = SimpleNamespace(
        timeline_in_ms=300,
        nested_audio_tracks=[[child_audio]],
        nested_tracks=lambda: [],
    )
    parent_clip = SimpleNamespace(
        timeline_in_ms=100,
        nested_audio_tracks=[[_audio_clip(id=9, offset_ms=5, effective_length_ms=40), nested_audio]],
        nested_tracks=lambda: [[child_clip]],
    )
    owner = SimpleNamespace(_tracks=[SimpleNamespace(clips=[parent_clip])])

    clips = bridge.collect_nested_audio_preview_clips(owner)

    assert [clip.id for clip in clips] == [-100000, -100001, -100002]
    assert [clip.offset_ms for clip in clips] == [105, 107, 411]
    assert [clip.effective_length_ms for clip in clips] == [40, 50, 60]
    assert nested_audio.id == 10


def test_sync_nested_audio_preview_track_updates_hidden_track_and_removes_empty() -> None:
    log: list[str] = []
    clip = SimpleNamespace(
        timeline_in_ms=200,
        nested_audio_tracks=[[_audio_clip(offset_ms=25, effective_length_ms=75)]],
        nested_tracks=lambda: [],
    )
    owner = SimpleNamespace(
        _tracks=[SimpleNamespace(clips=[clip])],
        _audio_mixer=_Mixer(log),
    )

    extent = bridge.sync_nested_audio_preview_track(
        owner,
        audio_track_factory=_FakeAudioTrack,
    )

    assert extent == 300
    assert log == ["mixer.update:-9001:Nested audio preview"]
    assert owner._audio_mixer.updated.clips[0].offset_ms == 225

    empty_owner = SimpleNamespace(_tracks=[], _audio_mixer=_Mixer(log))
    assert bridge.sync_nested_audio_preview_track(empty_owner) == 0
    assert log[-1] == "mixer.remove:-9001"


def test_collect_video_embedded_audio_preview_clips_skips_linked_or_duplicate_audio() -> None:
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip

    source = Path("camera.mp4")
    linked_audio = AudioClip(
        id=20,
        source_path=source,
        duration_ms=5000,
        offset_ms=0,
        trim_start_ms=0,
        trim_end_ms=1000,
    )
    duplicate_audio = AudioClip(
        id=21,
        source_path=source,
        duration_ms=5000,
        offset_ms=3000,
        trim_start_ms=1000,
        trim_end_ms=1800,
    )
    linked_video = VideoClip(
        id=10,
        source_path=source,
        source_duration_ms=5000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=1000,
        linked_audio_id=20,
    )
    duplicate_video = VideoClip(
        id=11,
        source_path=source,
        source_duration_ms=5000,
        timeline_in_ms=3000,
        source_in_ms=1000,
        source_out_ms=1800,
    )
    audible_video = VideoClip(
        id=12,
        source_path=source,
        source_duration_ms=5000,
        timeline_in_ms=5000,
        source_in_ms=1800,
        source_out_ms=2600,
    )
    owner = SimpleNamespace(
        _tracks=[SimpleNamespace(id=1, clips=[linked_video, duplicate_video, audible_video])],
        _audio_tracks=[AudioTrack(id=2, clips=[linked_audio, duplicate_audio])],
    )

    clips = bridge.collect_video_embedded_audio_preview_clips(owner)

    assert len(clips) == 1
    assert clips[0].id == -200000
    assert clips[0].source_path == source
    assert clips[0].offset_ms == 5000
    assert clips[0].trim_start_ms == 1800
    assert clips[0].trim_end_ms == 2600
    assert getattr(clips[0], "preview_embedded_video_audio") is True


def test_sync_video_embedded_audio_preview_track_updates_hidden_track() -> None:
    from app.timeline_model import VideoClip

    log: list[str] = []
    clip = VideoClip(
        id=10,
        source_path=Path("clip.mp4"),
        source_duration_ms=4000,
        timeline_in_ms=250,
        source_in_ms=500,
        source_out_ms=1800,
    )
    owner = SimpleNamespace(
        _tracks=[SimpleNamespace(id=1, clips=[clip])],
        _audio_tracks=[],
        _audio_mixer=_Mixer(log),
    )

    extent = bridge.sync_video_embedded_audio_preview_track(
        owner,
        audio_track_factory=_FakeAudioTrack,
    )

    assert extent == 1550
    assert log == ["mixer.update:-9002:Embedded video audio preview"]
    assert owner._audio_mixer.updated.clips[0].offset_ms == 250
    assert owner._audio_mixer.updated.clips[0].trim_start_ms == 500
    assert owner._audio_mixer.updated.clips[0].trim_end_ms == 1800


def test_video_embedded_audio_preview_follows_timeline_with_editor_state() -> None:
    from app.audio_tracks import AudioClip
    from app.timeline_model import VideoClip

    source = Path("scene.mp4")
    clip = VideoClip(
        id=32,
        source_path=source,
        source_duration_ms=9000,
        timeline_in_ms=1000,
        source_in_ms=1500,
        source_out_ms=3600,
    )
    proxy = AudioClip(
        id=-300032,
        source_path=source,
        duration_ms=9000,
        offset_ms=1000,
        trim_start_ms=1500,
        trim_end_ms=3600,
        fade_in_ms=120,
        fade_out_ms=240,
        gain=0.42,
    )
    proxy.effects["eq"]["low"]["gain"] = 4.5
    setattr(proxy, "_se_speed", 1.2)
    setattr(clip, "_embedded_audio_proxy_clip", proxy)
    owner = SimpleNamespace(
        _tracks=[SimpleNamespace(id=1, clips=[clip])],
        _audio_tracks=[],
    )

    [audio_clip] = bridge.collect_video_embedded_audio_preview_clips(owner)

    assert audio_clip.offset_ms == 1000
    assert audio_clip.trim_start_ms == 1500
    assert audio_clip.trim_end_ms == 3600
    assert audio_clip.gain == 0.42
    assert audio_clip.fade_in_ms == 120
    assert audio_clip.fade_out_ms == 240
    assert audio_clip.effects["eq"]["low"]["gain"] == 4.5
    assert getattr(audio_clip, "_se_speed") == 1.2

    clip.timeline_in_ms = 4200
    clip.source_in_ms = 2300
    clip.source_out_ms = 5200
    [moved_audio_clip] = bridge.collect_video_embedded_audio_preview_clips(owner)

    assert moved_audio_clip.offset_ms == 4200
    assert moved_audio_clip.trim_start_ms == 2300
    assert moved_audio_clip.trim_end_ms == 5200
    assert moved_audio_clip.gain == 0.42
    assert moved_audio_clip.effects["eq"]["low"]["gain"] == 4.5


class _RefreshPlayer:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def set_project_settings(self, settings) -> None:
        self.log.append(f"player.settings:{settings['fps']}")

    def set_ar_pbr_tracks(self, tracks) -> None:
        self.log.append(f"player.ar:{len(tracks)}")

    def set_mmd_tracks(self, tracks) -> None:
        self.log.append(f"player.mmd:{len(tracks)}")

    def set_spine_actor_tracks(self, tracks) -> None:
        self.log.append(f"player.spine:{len(tracks)}")

    def set_live2d_actor_tracks(self, tracks) -> None:
        self.log.append(f"player.live2d:{len(tracks)}")

    def refresh_tracks(self, tracks, *, extra_duration_ms=0, render_immediately=True) -> None:
        self.log.append(
            f"player.refresh:{len(tracks)}:{extra_duration_ms}:{render_immediately}"
        )


class _RefreshOwner:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self._player = _RefreshPlayer(log)
        self._project_settings = {"fps": 24}
        self._tracks = [SimpleNamespace(clips=[])]
        self._audio_tracks = [
            SimpleNamespace(extent_ms=lambda: 420),
        ]
        self._spine_actor_tracks = [SimpleNamespace(clips=[SimpleNamespace(end_ms=510)])]
        self._live2d_actor_tracks = [SimpleNamespace(clips=[SimpleNamespace(end_ms=620)])]
        self._ar_pbr_tracks = [{"end_ms": 730}]
        self._mmd_tracks = [{"end_ms": 840}]
        self._track_rows = {
            1: _Row("video1", log),
            2: _Row("video2", log),
        }
        self._audio_rows = {1: _Row("audio1", log)}
        self._actor_lane_rows = [_Row("actor1", log)]
        self._live2d_lane_rows = [_Row("live2d1", log)]
        self._ar_pbr_lane_rows = [_Row("ar1", log)]
        self._mmd_lane_rows = [_Row("mmd1", log)]

    def _sync_ar_pbr_tracks_to_player(self) -> None:
        self.log.append("owner.sync_ar")
        bridge.sync_ar_pbr_tracks_to_player(self)

    def _sync_mmd_tracks_to_player(self) -> None:
        self.log.append("owner.sync_mmd")
        bridge.sync_mmd_tracks_to_player(self)

    def _sync_actor_tracks_to_player(self) -> None:
        self.log.append("owner.sync_actor")
        bridge.sync_actor_tracks_to_player(self)

    def _refresh_preview_canvas_interaction_hook(self) -> None:
        self.log.append("owner.preview_hook")

    def _update_preview_placeholder(self) -> None:
        self.log.append("owner.placeholder")

    def _refresh_proxy_status_ui(self) -> None:
        self.log.append("owner.proxy")


def test_refresh_player_tracks_preserves_sync_refresh_and_repaint_order() -> None:
    log: list[str] = []
    owner = _RefreshOwner(log)

    bridge.refresh_player_tracks(owner, render_immediately=False)

    assert log == [
        "player.settings:24",
        "owner.sync_ar",
        "player.ar:1",
        "owner.sync_mmd",
        "player.mmd:1",
        "owner.sync_actor",
        "player.spine:1",
        "player.live2d:1",
        "owner.preview_hook",
        "player.refresh:1:840:False",
        "owner.placeholder",
        "video1.update",
        "video2.update",
        "audio1.update",
        "actor1.update",
        "live2d1.update",
        "ar1.update",
        "mmd1.update",
        "owner.proxy",
    ]


class _PlayButton:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def setText(self, text: str) -> None:
        self.log.append(f"button.text:{text}")

    def setIcon(self, icon) -> None:
        self.log.append(f"button.icon:{icon}")

    def setIconSize(self, size) -> None:
        self.log.append(f"button.size:{size}")


class _PlaybackPopout:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def set_playing(self, playing: bool) -> None:
        self.log.append(f"popout.playing:{playing}")


def test_on_playback_state_changed_updates_button_then_popout() -> None:
    log: list[str] = []
    owner = SimpleNamespace(
        play_btn=_PlayButton(log),
        _preview_popout=_PlaybackPopout(log),
    )

    bridge.on_playback_state_changed(
        owner,
        PlayerState.PLAYING,
        icon_factory=lambda name, **_kwargs: f"icon:{name}",
        icon_size_factory=lambda size: f"size:{size}",
    )

    assert log == [
        "button.text:",
        "button.icon:icon:pause",
        "button.size:size:14",
        "popout.playing:True",
    ]


class _TimelineRuler:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def set_playhead(self, pos: int) -> None:
        self.log.append(f"ruler.playhead:{pos}")

    def set_project_duration(self, duration: int) -> None:
        self.log.append(f"ruler.duration:{duration}")


class _MixerPanel:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def isVisible(self) -> bool:
        return True

    def update_levels(self, pos: int, tracks) -> None:
        self.log.append(f"mixer_panel.levels:{pos}:{len(tracks)}")

    def update_scopes(self, pos: int, tracks) -> None:
        self.log.append(f"mixer_panel.scopes:{pos}:{len(tracks)}")


class _PositionPopout:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def set_time_text(self, text: str) -> None:
        self.log.append(f"popout.time:{text}")


class _Canvas:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def update(self) -> None:
        self.log.append("canvas.update")


class _DurationPlayer:
    def duration(self) -> int:
        return 2500


class _PositionOwner:
    def __init__(self, log: list[str]) -> None:
        waveform = np.zeros(20, dtype=float)
        waveform[5] = 0.4
        audio_clip = _audio_clip(
            offset_ms=1000,
            effective_length_ms=2000,
            waveform=waveform,
        )
        self.log = log
        self._track_rows = {1: _Row("video1", log)}
        self._audio_rows = {7: _Row("audio7", log)}
        self._actor_lane_rows = [_Row("actor1", log)]
        self._live2d_lane_rows = [_Row("live2d1", log)]
        self._ar_pbr_lane_rows = [_Row("ar1", log)]
        self._mmd_lane_rows = [_Row("mmd1", log)]
        self._timeline_ruler = _TimelineRuler(log)
        self._audio_tracks = [
            SimpleNamespace(id=7, volume=2.0, clips=[audio_clip]),
        ]
        self._waveform_buckets_per_sec = 10
        self._audio_mixer_panel = _MixerPanel(log)
        self._player = _DurationPlayer()
        self.time_label = _Label(log)
        self._preview_popout = _PositionPopout(log)
        self._drawing_canvas = _Canvas(log)
        self._current_segment_speed = 1.0
        self._jkl_transport_rate = 0.0
        self._tracks = [
            SimpleNamespace(
                source_path="clip.mp4",
                clips=[],
                cuts=[],
                offset_ms=0,
                duration_ms=3000,
            )
        ]

    def _push_snap_targets_to_rows(self) -> None:
        self.log.append("owner.snap")

    def _update_subtitle_overlay(self, pos: int) -> None:
        self.log.append(f"owner.subtitle:{pos}")

    def _scale_preview_to_fit(self) -> None:
        self.log.append("owner.scale")

    def _sync_pip_sliders_to_position(self, pos: int) -> None:
        self.log.append(f"owner.pip:{pos}")

    def _update_bubble_visibility(self, pos: int) -> None:
        self.log.append(f"owner.bubble:{pos}")

    def _update_sticker_visibility(self, pos: int) -> None:
        self.log.append(f"owner.sticker:{pos}")

    def _update_text_clip_overlay(self, pos: int) -> None:
        self.log.append(f"owner.text:{pos}")

    def _speed_at(self, track, pos_ms: int) -> float:
        self.log.append(f"owner.speed_at:{pos_ms}")
        return 0.5

    def _set_transport_speed_label(self, speed: float) -> None:
        self.log.append(f"owner.speed_label:{speed:g}")


def test_on_position_changed_preserves_row_meter_ui_and_speed_order() -> None:
    log: list[str] = []
    owner = _PositionOwner(log)

    bridge.on_position_changed(owner, 1500)

    assert log == [
        "video1.set_position:1500",
        "audio7.set_position:1500",
        "actor1.set_playhead:1500",
        "live2d1.set_playhead:1500",
        "ar1.set_playhead:1500",
        "mmd1.set_playhead:1500",
        "ruler.playhead:1500",
        "owner.snap",
        "audio7.level:0.80:0.80",
        "mixer_panel.levels:1500:1",
        "mixer_panel.scopes:1500:1",
        "label.text:0:01 / 0:02",
        "popout.time:0:01 / 0:02",
        "owner.subtitle:1500",
        "owner.scale",
        "canvas.update",
        "owner.pip:1500",
        "owner.bubble:1500",
        "owner.sticker:1500",
        "owner.text:1500",
        "owner.speed_at:1500",
        "owner.speed_label:0.5",
    ]


class _SubtitlePanel:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def set_project_duration(self, duration: int) -> None:
        self.log.append(f"subtitle.duration:{duration}")


class _DurationOwner:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self._track_rows = {1: _Row("video1", log), 2: _Row("video2", log)}
        self._timeline_ruler = _TimelineRuler(log)
        self.time_label = _Label(log)
        self._subtitle_panel = _SubtitlePanel(log)

    def _update_tracks_host_width(self) -> None:
        self.log.append("owner.host_width")

    def _refresh_workbench(self) -> None:
        self.log.append("owner.workbench")


def test_on_duration_changed_preserves_recalc_then_project_ui_order() -> None:
    log: list[str] = []
    owner = _DurationOwner(log)

    bridge.on_duration_changed(owner, 65000)

    assert log == [
        "video1.recalc",
        "video2.recalc",
        "ruler.duration:65000",
        "owner.host_width",
        "label.text:0:00 / 1:05",
        "subtitle.duration:65000",
        "owner.workbench",
    ]
