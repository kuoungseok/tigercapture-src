from __future__ import annotations

from pathlib import Path


class _ProjectIoPlayer:
    REFERENCE_FPS = 30.0

    def __init__(self) -> None:
        self._position = 0

    def position(self) -> int:
        return self._position

    def pause(self) -> None:
        pass

    def set_position(self, value: int) -> None:
        self._position = int(value)


class _NoopLayout:
    def removeWidget(self, _widget) -> None:
        pass


class _ProjectIoEditor:
    def __init__(self) -> None:
        self._player = _ProjectIoPlayer()
        self._project_settings = {}
        self._px_per_sec = 40.0
        self._global_in_ms = -1
        self._global_out_ms = -1
        self._tracks = []
        self._track_rows = {}
        self._audio_tracks = []
        self._audio_rows = {}
        self._tracks_layout = _NoopLayout()
        self._next_track_id = 1
        self._next_audio_track_id = 1
        self._next_audio_clip_id = 1
        self._audio_mixer_snapshots = []
        self._music_compositions = {}
        self.inserted_audio_tracks = []
        self.waveform_clips = []
        self.refresh_count = 0
        self.width_refresh_count = 0

    def _change_zoom(self, value: float) -> None:
        self._px_per_sec *= float(value)

    def _set_global_in(self, value: int) -> None:
        self._global_in_ms = int(value)

    def _set_global_out(self, value: int) -> None:
        self._global_out_ms = int(value)

    def _refresh_player_tracks(self) -> None:
        self.refresh_count += 1

    def _update_tracks_host_width(self) -> None:
        self.width_refresh_count += 1

    def _insert_audio_track_widget(self, track) -> None:
        self.inserted_audio_tracks.append(track)

    def _start_waveform_extraction(self, clip) -> None:
        self.waveform_clips.append(clip)

    def _clear_global_markers(self) -> None:
        self._timeline_markers = []

    def setWindowTitle(self, _title: str) -> None:
        pass


def test_project_io_persists_music_lab_compositions_and_track_links(tmp_path: Path) -> None:
    from app.audio_tracks import AudioClip, AudioTrack
    from app.music_composer import compose_music, render_preview
    from app.project_io import load_project, save_project

    composition = compose_music(prompt="project save bgm", duration_ms=5000, genre="lofi", mood="chill")
    render_preview(composition, output_dir=tmp_path)
    music_role = "percussion"
    stem_path = Path(composition.rendered_stems[music_role])

    clip = AudioClip(
        id=20,
        source_path=stem_path,
        duration_ms=composition.duration_ms,
        offset_ms=100,
        trim_start_ms=0,
        trim_end_ms=composition.duration_ms,
    )
    clip.music_composition_id = composition.id
    clip.music_role = music_role
    track = AudioTrack(id=2, clips=[clip], label="Music Percussion", bus_id="music", track_type="music")
    track.music_composition_id = composition.id
    track.music_role = music_role

    editor = _ProjectIoEditor()
    editor._audio_tracks = [track]
    editor._music_compositions = {composition.id: composition}
    project_path = tmp_path / "music_project.tgp"

    save_project(editor, project_path)

    loaded = _ProjectIoEditor()
    load_project(loaded, project_path)

    assert composition.id in loaded._music_compositions
    loaded_composition = loaded._music_compositions[composition.id]
    assert loaded_composition.prompt == "project save bgm"
    assert loaded_composition.rendered_stems[music_role] == str(stem_path)
    assert len(loaded._audio_tracks) == 1
    loaded_track = loaded._audio_tracks[0]
    assert loaded_track.music_composition_id == composition.id
    assert loaded_track.music_role == music_role
    assert loaded_track.clips[0].music_composition_id == composition.id
    assert loaded_track.clips[0].music_role == music_role
