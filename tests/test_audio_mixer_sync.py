from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from app.audio_tracks import AudioClip, AudioMixer, AudioTrack


def _qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class _FakePlayer:
    def __init__(self, *, position: int = 0, playing: bool = False) -> None:
        self._position = int(position)
        self._state = (
            QMediaPlayer.PlaybackState.PlayingState
            if playing
            else QMediaPlayer.PlaybackState.PausedState
        )
        self.set_positions: list[int] = []
        self.play_count = 0
        self.pause_count = 0

    def position(self) -> int:
        return self._position

    def setPosition(self, ms: int) -> None:
        self._position = int(ms)
        self.set_positions.append(int(ms))

    def playbackState(self):
        return self._state

    def play(self) -> None:
        self._state = QMediaPlayer.PlaybackState.PlayingState
        self.play_count += 1

    def pause(self) -> None:
        self._state = QMediaPlayer.PlaybackState.PausedState
        self.pause_count += 1


class _FakeOutput:
    pass


def test_audio_mixer_does_not_reseek_every_playing_tick(monkeypatch) -> None:
    _qapp()
    mixer = AudioMixer()
    clip = AudioClip(
        id=1,
        source_path=Path("voice.wav"),
        duration_ms=1000,
        trim_end_ms=1000,
    )
    player = _FakePlayer(position=33, playing=True)
    mixer._tracks = {1: AudioTrack(id=1, clips=[clip])}
    mixer._players = {1: (player, _FakeOutput(), 1)}
    mixer._project_playing = True
    mixer._project_position_ms = 0
    mixer._active_clip_ids = {1}
    monkeypatch.setattr(mixer, "_ensure_source_loaded", lambda _player, _clip: False)

    mixer.on_position_changed(33)

    assert player.set_positions == []
    assert player.play_count == 0


def test_audio_mixer_starts_clip_when_playhead_enters_window(monkeypatch) -> None:
    _qapp()
    mixer = AudioMixer()
    clip = AudioClip(
        id=1,
        source_path=Path("voice.wav"),
        duration_ms=1000,
        offset_ms=100,
        trim_end_ms=1000,
    )
    player = _FakePlayer(position=0, playing=False)
    mixer._tracks = {1: AudioTrack(id=1, clips=[clip])}
    mixer._players = {1: (player, _FakeOutput(), 1)}
    mixer._project_playing = True
    mixer._project_position_ms = 67
    monkeypatch.setattr(mixer, "_ensure_source_loaded", lambda _player, _clip: False)

    mixer.on_position_changed(100)

    assert player.set_positions == [0]
    assert player.play_count == 1
    assert mixer._active_clip_ids == {1}


def test_audio_mixer_preloads_upcoming_clip_without_playing(monkeypatch) -> None:
    _qapp()
    mixer = AudioMixer()
    clip = AudioClip(
        id=1,
        source_path=Path("voice.wav"),
        duration_ms=2000,
        offset_ms=1200,
        trim_start_ms=300,
        trim_end_ms=2000,
    )
    player = _FakePlayer(position=0, playing=False)
    mixer._tracks = {1: AudioTrack(id=1, clips=[clip])}
    mixer._players = {1: (player, _FakeOutput(), 1)}
    mixer._project_playing = True
    mixer._project_position_ms = 0
    loads: list[int] = []

    def fake_load(_player, loaded_clip):
        loads.append(int(loaded_clip.id))
        return True

    monkeypatch.setattr(mixer, "_ensure_source_loaded", fake_load)

    mixer.on_position_changed(100)

    assert loads == [1]
    assert player.set_positions == [300]
    assert player.play_count == 0
    assert mixer._active_clip_ids == set()


def test_audio_mixer_does_not_preload_distant_clip(monkeypatch) -> None:
    _qapp()
    mixer = AudioMixer()
    clip = AudioClip(
        id=1,
        source_path=Path("voice.wav"),
        duration_ms=2000,
        offset_ms=5000,
        trim_start_ms=300,
        trim_end_ms=2000,
    )
    player = _FakePlayer(position=0, playing=False)
    mixer._tracks = {1: AudioTrack(id=1, clips=[clip])}
    mixer._players = {1: (player, _FakeOutput(), 1)}
    mixer._project_playing = True
    loads: list[int] = []
    monkeypatch.setattr(mixer, "_ensure_source_loaded", lambda _player, loaded_clip: loads.append(int(loaded_clip.id)) or True)

    mixer.on_position_changed(100)

    assert loads == []
    assert player.set_positions == []
    assert player.play_count == 0
