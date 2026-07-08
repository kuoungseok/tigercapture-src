from __future__ import annotations

from types import SimpleNamespace

from app.simple_video_player import PlayerState
from app.timeline_model import VideoClip, VideoTrack
from app import video_editor_timeline_operations as timeline_ops
from app import video_editor_transport_workflow as transport


class _FakePlayer:
    def __init__(self, *, state=PlayerState.PAUSED, position=0) -> None:
        self._state = state
        self._position = int(position)
        self.paused = False
        self.played = False
        self.set_positions: list[int] = []
        self.play_until_calls: list[tuple[int, int | None]] = []

    def state(self):
        return self._state

    def position(self) -> int:
        return self._position

    def set_position(self, ms: int) -> None:
        self._position = int(ms)
        self.set_positions.append(int(ms))

    def play_until(self, end_ms: int, *, return_to_ms: int | None = None) -> None:
        self.play_until_calls.append((int(end_ms), None if return_to_ms is None else int(return_to_ms)))

    def play(self) -> None:
        self.played = True

    def pause(self) -> None:
        self.paused = True


def _owner_with_player(player: _FakePlayer) -> SimpleNamespace:
    track = VideoTrack(
        id=1,
        clips=[
            VideoClip(
                id=10,
                source_path="clip.mp4",
                source_duration_ms=1000,
                timeline_in_ms=1000,
                source_in_ms=0,
                source_out_ms=1000,
            )
        ],
    )
    owner = SimpleNamespace(
        _player=player,
        _tracks=[track],
        _selected_clips=[],
        _jkl_transport_rate=1.0,
        flashes=[],
    )
    owner._find_track = lambda track_id: track if int(track_id) == 1 else None
    owner._clip_audition_range = lambda: timeline_ops._clip_audition_range(owner)
    owner._ensure_playback_rate_for_play = lambda: None
    owner._flash_status = lambda text: owner.flashes.append(str(text))
    return owner


def test_toggle_play_pauses_when_already_playing() -> None:
    player = _FakePlayer(state=PlayerState.PLAYING, position=1200)
    owner = _owner_with_player(player)

    transport._toggle_play(owner)

    assert player.paused is True
    assert player.play_until_calls == []
    assert player.played is False


def test_toggle_play_auditions_selected_clip_and_restores_playhead() -> None:
    player = _FakePlayer(position=500)
    owner = _owner_with_player(player)
    owner._selected_clips = [(1, 10)]

    transport._toggle_play(owner)

    assert player.set_positions == [1000]
    assert player.play_until_calls == [(2000, 500)]
    assert player.played is False
    assert any("returns to playhead" in item for item in owner.flashes)


def test_toggle_play_falls_back_to_project_play_when_no_clip_range() -> None:
    player = _FakePlayer(position=5000)
    owner = _owner_with_player(player)

    transport._toggle_play(owner)

    assert player.played is True
    assert player.play_until_calls == []
