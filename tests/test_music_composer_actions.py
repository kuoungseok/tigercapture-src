from __future__ import annotations

from pathlib import Path

import pytest


class _MusicActionOwner:
    def __init__(self) -> None:
        self._audio_tracks = []
        self._tracks = []
        self._next_track_id = 1
        self._audio_rows = {}
        self._music_compositions = {}
        self.inserted_tracks = []
        self.waveform_clips = []
        self.changes = []
        self.refresh_count = 0
        self.width_refresh_count = 0

    def _insert_audio_track_widget(self, track) -> None:
        self.inserted_tracks.append(track)

    def _start_waveform_extraction(self, clip) -> None:
        self.waveform_clips.append(clip)

    def _refresh_player_tracks(self) -> None:
        self.refresh_count += 1

    def _update_tracks_host_width(self) -> None:
        self.width_refresh_count += 1

    def _register_change(self, label: str = "") -> None:
        self.changes.append(label)


def test_music_actions_compose_render_and_insert_timeline(tmp_path: Path) -> None:
    from app.actions import build_default_action_registry

    owner = _MusicActionOwner()
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}
    assert {
        "music.compose",
        "music.render.preview",
        "music.render.backends",
        "music.render_to_timeline",
        "music.export_midi",
        "music.mixer.auto_balance",
        "music.state",
        "midi.clip.create",
        "midi.clip.write_notes",
        "midi.clip.quantize",
    } <= ids

    composed = registry.execute(
        "music.compose",
        {
            "prompt": "short energetic tech demo bed",
            "duration_ms": 8000,
            "genre": "electronic",
            "mood": "confident",
            "bpm": 120,
            "key": "C minor",
        },
    ).to_dict()
    assert composed["ok"] is True
    composition_id = composed["result"]["summary"]["id"]
    assert composed["result"]["summary"]["track_count"] >= 4
    assert composed["result"]["summary"]["note_count"] > 0

    rendered = registry.execute(
        "music.render.preview",
        {"composition_id": composition_id, "output_dir": str(tmp_path)},
    ).to_dict()
    assert rendered["ok"] is True
    assert Path(rendered["result"]["preview_mix_path"]).exists()
    assert Path(rendered["result"]["preview_mix_path"]).stat().st_size > 44
    assert all(Path(path).exists() for path in rendered["result"]["stems"].values())
    assert rendered["result"]["render_engine"] in {
        "tigerstudio.local_synth.v5",
        "fluidsynth.soundfont.v1",
        "tigerstudio.studio_edm.v1",
    }
    assert rendered["result"]["render_backend"]["backend"] in {"local_synth", "fluidsynth_soundfont", "studio_edm"}
    assert rendered["result"]["render_backend"]["quality_tier"] in {"draft_sketch", "starter_preview"}
    assert rendered["result"]["render_backend"]["production_ready"] is False

    local_rendered = registry.execute(
        "music.render.preview",
        {"composition_id": composition_id, "output_dir": str(tmp_path), "backend": "local_synth"},
    ).to_dict()
    assert local_rendered["ok"] is True
    assert local_rendered["result"]["render_engine"] == "tigerstudio.local_synth.v5"
    assert local_rendered["result"]["render_backend"]["backend"] == "local_synth"
    assert local_rendered["result"]["render_backend"]["quality_tier"] == "draft_sketch"
    assert local_rendered["result"]["render_backend"]["production_ready"] is False

    backends = registry.execute("music.render.backends", {}).to_dict()
    assert backends["ok"] is True
    assert backends["result"]["preferred_backend"] in {"local_synth", "fluidsynth_soundfont", "production_external"}
    assert backends["result"]["quality_tiers"]["fluidsynth_soundfont"] == "starter_preview"
    assert backends["result"]["quality_tiers"]["production_external"] == "production_candidate"
    assert "quality_warning" in backends["result"]
    assert any("external" in path and "soundfonts" in path for path in backends["result"]["asset_dirs"])

    inserted = registry.execute(
        "music.render_to_timeline",
        {"composition_id": composition_id, "output_dir": str(tmp_path), "at_ms": 500, "roles": ["drums", "bass"]},
    ).to_dict()
    assert inserted["ok"] is True
    assert inserted["result"]["added_count"] == 2
    assert len(owner._audio_tracks) == 2
    assert len(owner.inserted_tracks) == 2
    assert len(owner.waveform_clips) == 2
    assert {getattr(track, "track_type") for track in owner._audio_tracks} == {"music"}
    assert {getattr(track, "bus_id") for track in owner._audio_tracks} == {"music"}
    assert {track.clips[0].offset_ms for track in owner._audio_tracks} == {500}

    updated = registry.execute(
        "music.render_to_timeline",
        {
            "composition_id": composition_id,
            "output_dir": str(tmp_path),
            "at_ms": 750,
            "roles": ["drums", "bass"],
            "update_existing": True,
        },
    ).to_dict()
    assert updated["ok"] is True
    assert updated["result"]["added_count"] == 0
    assert updated["result"]["updated_count"] == 2
    assert len(owner._audio_tracks) == 2
    assert len(owner.inserted_tracks) == 2
    assert {track.clips[0].offset_ms for track in owner._audio_tracks} == {750}

    midi = registry.execute(
        "music.export_midi",
        {"composition_id": composition_id, "output_dir": str(tmp_path)},
    ).to_dict()
    assert midi["ok"] is True
    midi_path = Path(midi["result"]["path"])
    assert midi_path.exists()
    assert midi_path.read_bytes().startswith(b"MThd")

    balanced = registry.execute("music.mixer.auto_balance", {"composition_id": composition_id}).to_dict()
    assert balanced["ok"] is True
    assert balanced["result"]["changed_count"] == 2
    assert all(0.0 <= track.volume <= 1.5 for track in owner._audio_tracks)

    state = registry.execute("music.state", {"composition_id": composition_id}).to_dict()
    assert state["ok"] is True
    assert state["result"]["composition"]["id"] == composition_id


def test_music_compose_to_timeline_wraps_create_render_insert_and_balance(tmp_path: Path) -> None:
    from app.actions import build_default_action_registry

    owner = _MusicActionOwner()
    registry = build_default_action_registry(owner)
    result = registry.execute(
        "music.compose_to_timeline",
        {
            "prompt": "12s lofi background music",
            "duration_ms": 12000,
            "genre": "lofi",
            "mood": "chill",
            "output_dir": str(tmp_path),
            "at_ms": 1000,
            "roles": ["drums", "chords"],
            "auto_balance": True,
        },
    ).to_dict()

    assert result["ok"] is True
    composition_id = result["result"]["composition_id"]
    assert composition_id in owner._music_compositions
    assert result["result"]["composition"]["id"] == composition_id
    assert result["result"]["composition"]["tracks"]
    assert result["result"]["composition"]["preview_mix_path"] == result["result"]["preview"]["preview_mix_path"]
    assert result["result"]["composition"]["rendered_stems"]
    assert Path(result["result"]["preview"]["preview_mix_path"]).exists()
    assert result["result"]["timeline"]["added_count"] == 2
    assert result["result"]["mixer"]["changed_count"] == 2
    assert {track.clips[0].offset_ms for track in owner._audio_tracks} == {1000}


def test_music_default_uses_9_channel_baseline() -> None:
    from app.music_composer import DEFAULT_MUSIC_TRACK_COUNT, compose_music

    composition = compose_music(
        prompt="simple creator background music",
        duration_ms=12000,
        genre="creator bgm",
        mood="calm",
        bpm=104,
        key="C minor",
    )
    roles = [track.role for track in composition.tracks]

    assert len(composition.tracks) == DEFAULT_MUSIC_TRACK_COUNT
    assert roles == ["drums", "bass", "bass_pulse", "chords", "arp", "melody", "lead_answer", "counter", "fx"]
    assert sum(len(clip.notes) for track in composition.tracks for clip in track.clips) > 0


def test_music_key_aware_chord_progressions_and_edm_sections() -> None:
    from app.music_composer import TICKS_PER_BEAT, chord_progression_for, compose_music, ms_to_tick

    assert chord_progression_for("A minor", "melodic EDM", "bright") == ["Am", "F", "C", "G"]
    assert chord_progression_for("C minor", "cinematic", "dark") == ["Cm", "Ab", "Eb", "Bb"]
    assert chord_progression_for("C major", "creator", "bright") == ["C", "Am", "F", "G"]

    composition = compose_music(
        prompt="original NCS melodic EDM with breakdown variation",
        duration_ms=45000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    assert [section.name for section in composition.sections] == ["intro", "build", "drop_1", "breakdown", "drop_2_outro"]
    assert composition.sections[0].chord_progression == ["Am", "F", "C", "G"]
    assert composition.sections[3].chord_progression == ["F", "G", "Am", "Em"]
    assert composition.sections[4].chord_progression == ["C", "G", "Am", "F"]
    assert composition.duration_ms == 45000

    bar_ticks = TICKS_PER_BEAT * 4
    sections_by_name = {section.name: section for section in composition.sections}
    for section in composition.sections:
        assert ms_to_tick(section.start_ms, composition.bpm) % bar_ticks == 0
        assert ms_to_tick(section.duration_ms, composition.bpm) % bar_ticks == 0
    for track in composition.tracks:
        for clip in track.clips:
            section = sections_by_name[clip.section_name]
            section_start_tick = ms_to_tick(section.start_ms, composition.bpm)
            section_end_tick = ms_to_tick(section.start_ms + section.duration_ms, composition.bpm)
            for note in clip.notes:
                assert note.start_tick >= section_start_tick
                assert note.start_tick + note.duration_tick <= section_end_tick


def test_music_preview_can_render_mix_without_stem_wavs(tmp_path: Path) -> None:
    from app.music_composer import compose_music, render_preview

    composition = compose_music(
        prompt="clean melodic edm preview",
        duration_ms=6000,
        genre="electronic",
        mood="bright",
        bpm=128,
        key="A minor",
    )
    output_dir = tmp_path / "mix_only"
    rendered = render_preview(composition, output_dir=output_dir, backend="local_synth", render_stems=False)

    mix_path = Path(rendered["preview_mix_path"])
    role_wavs = [path for path in output_dir.glob(f"{composition.id}_*.wav") if path.name != f"{composition.id}_mix.wav"]
    assert mix_path.exists()
    assert rendered["stems"] == {}
    assert composition.rendered_stems == {}
    assert composition.render_backend["render_stems"] is False
    assert role_wavs == []


def test_studio_edm_preview_backend_is_mix_only_when_requested(tmp_path: Path) -> None:
    from app.music_composer import compose_music, render_preview

    composition = compose_music(
        prompt="original NCS style melodic EDM studio preview",
        duration_ms=12000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    output_dir = tmp_path / "studio_edm"
    rendered = render_preview(composition, output_dir=output_dir, backend="studio_edm", render_stems=False)

    assert rendered["render_engine"] == "tigerstudio.studio_edm.v1"
    assert rendered["render_backend"]["backend"] == "studio_edm"
    assert rendered["stems"] == {}
    assert Path(rendered["preview_mix_path"]).exists()
    assert sorted(path.name for path in output_dir.glob("*.wav")) == [f"{composition.id}_mix.wav"]


def test_auto_preview_prefers_soundfont_before_draft_edm(tmp_path: Path, monkeypatch) -> None:
    import app.music_composer as music_composer

    composition = music_composer.compose_music(
        prompt="original NCS style melodic EDM studio preview",
        duration_ms=12000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    calls: list[str] = []
    soundfont = tmp_path / "real.sf2"
    soundfont.write_bytes(b"sf2")

    def fake_soundfont_preview(*args, **kwargs):
        calls.append("soundfont")
        composition.render_engine = "fluidsynth.soundfont.v1"
        composition.render_backend = {"backend": "fluidsynth_soundfont", "render_stems": False}
        mix_path = tmp_path / "auto_soundfont.wav"
        mix_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        composition.preview_mix_path = str(mix_path)
        return {
            "composition_id": composition.id,
            "output_dir": str(tmp_path),
            "stems": {},
            "preview_mix_path": str(mix_path),
            "render_engine": composition.render_engine,
            "render_backend": dict(composition.render_backend),
        }

    def fail_studio(*args, **kwargs):
        raise AssertionError("auto should not use the draft EDM synth while SoundFont rendering is ready")

    monkeypatch.setattr(music_composer, "_select_soundfont", lambda _path=None: soundfont)
    monkeypatch.setattr(music_composer, "find_fluidsynth_executable", lambda: "fluidsynth.exe")
    monkeypatch.setattr(
        music_composer,
        "music_production_renderer_status",
        lambda: {"ready": False, "backend": "production_external", "command": [], "supports_stems": False},
    )
    monkeypatch.setattr(music_composer, "_render_soundfont_preview", fake_soundfont_preview)
    monkeypatch.setattr(music_composer, "_render_studio_edm_preview", fail_studio)

    rendered = music_composer.render_preview(composition, output_dir=tmp_path, backend="auto", render_stems=False)

    assert calls == ["soundfont"]
    assert rendered["render_backend"]["backend"] == "fluidsynth_soundfont"


def test_auto_mix_only_preview_uses_configured_production_renderer(tmp_path: Path, monkeypatch) -> None:
    import app.music_composer as music_composer

    composition = music_composer.compose_music(
        prompt="modern EDM production preview",
        duration_ms=8000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )

    def fake_production_preview(*args, **kwargs):
        composition.render_engine = "production.external_music_renderer.v1"
        composition.render_backend = {
            "backend": "production_external",
            "quality_tier": "production_candidate",
            "production_ready": True,
            "render_stems": False,
        }
        mix_path = tmp_path / "production.wav"
        mix_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        composition.preview_mix_path = str(mix_path)
        return {
            "composition_id": composition.id,
            "output_dir": str(tmp_path),
            "stems": {},
            "preview_mix_path": str(mix_path),
            "render_engine": composition.render_engine,
            "render_backend": dict(composition.render_backend),
        }

    monkeypatch.setattr(
        music_composer,
        "music_production_renderer_status",
        lambda: {"ready": True, "backend": "production_external", "command": ["renderer"], "supports_stems": False},
    )
    monkeypatch.setattr(music_composer, "_render_external_production_preview", fake_production_preview)

    rendered = music_composer.render_preview(composition, output_dir=tmp_path, backend="auto", render_stems=False)

    assert rendered["render_backend"]["backend"] == "production_external"
    assert rendered["render_backend"]["quality_tier"] == "production_candidate"


def test_production_preview_requires_configured_renderer(tmp_path: Path, monkeypatch) -> None:
    import app.music_composer as music_composer

    composition = music_composer.compose_music(
        prompt="modern EDM release cue",
        duration_ms=8000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    monkeypatch.setattr(
        music_composer,
        "music_production_renderer_status",
        lambda: {
            "backend": "production_external",
            "ready": False,
            "configured": False,
            "command": [],
            "supports_stems": False,
            "quality_tier": "production_candidate",
            "warning": "No production renderer",
        },
    )

    with pytest.raises(RuntimeError, match="Production music rendering is not configured"):
        music_composer.render_preview(composition, output_dir=tmp_path, backend="production", render_stems=False)


def test_melodic_edm_music_uses_arranged_layers() -> None:
    from app.music_composer import compose_music

    composition = compose_music(
        prompt="original NCS style melodic EDM hook with variation",
        duration_ms=30000,
        genre="melodic EDM",
        mood="bright",
        bpm=128,
        key="A minor",
    )
    roles = {track.role for track in composition.tracks}

    assert len(composition.tracks) == 9
    assert {"drums", "bass", "bass_pulse", "chords", "arp", "melody", "lead_answer", "counter"} <= roles
    assert sum(len(clip.notes) for track in composition.tracks for clip in track.clips) > 0
    assert sum(len(clip.notes) for track in composition.tracks if track.role == "arp" for clip in track.clips) > 0
    assert sum(len(clip.notes) for track in composition.tracks if track.role == "lead_answer" for clip in track.clips) > 0


def test_orchestral_music_expands_to_128_internal_tracks(tmp_path: Path) -> None:
    from app.music_composer import MusicComposition, compose_music, export_midi, render_preview

    composition = compose_music(
        prompt="epic orchestral trailer score",
        duration_ms=4000,
        genre="orchestral",
        mood="epic",
        bpm=92,
        key="D minor",
    )

    roles = {track.role for track in composition.tracks}
    assert len(composition.tracks) == 128
    assert len(roles) == 128
    assert any(role.startswith("violins_i_") for role in roles)
    assert any(role.startswith("cellos_") for role in roles)
    assert any(role.startswith("horns_") for role in roles)
    assert any(role.startswith("flutes_") for role in roles)
    assert any(role.startswith("timpani_") for role in roles)
    assert any(role.startswith("orchestral_percussion_") for role in roles)
    assert sum(len(clip.notes) for track in composition.tracks for clip in track.clips) > 0

    midi = export_midi(composition, output_dir=tmp_path)
    assert midi["track_count"] == 128
    assert Path(midi["path"]).read_bytes().startswith(b"MThd")

    prefixes = (
        "violins_i_",
        "cellos_",
        "horns_",
        "flutes_",
        "timpani_",
        "orchestral_percussion_",
        "choir_",
        "hybrid_pad_",
    )
    render_tracks = [next(track for track in composition.tracks if track.role.startswith(prefix)) for prefix in prefixes]
    render_subset = MusicComposition(
        id=f"{composition.id}_orchestral_subset",
        prompt=composition.prompt,
        genre=composition.genre,
        mood=composition.mood,
        bpm=composition.bpm,
        key=composition.key,
        duration_ms=composition.duration_ms,
        sections=composition.sections,
        tracks=render_tracks,
    )
    rendered = render_preview(render_subset, output_dir=tmp_path, backend="local_synth")
    assert rendered["render_engine"] == "tigerstudio.local_synth.v5"
    assert len(rendered["stems"]) == len(prefixes)
    assert Path(rendered["preview_mix_path"]).exists()


def test_music_midi_clip_edit_actions(tmp_path: Path) -> None:
    from app.actions import build_default_action_registry

    owner = _MusicActionOwner()
    registry = build_default_action_registry(owner)
    composition_id = registry.execute(
        "music.compose",
        {"prompt": "minimal lofi loop", "duration_ms": 6000, "genre": "lofi", "mood": "chill"},
    ).to_dict()["result"]["summary"]["id"]

    created_track = registry.execute(
        "music.track.create",
        {"composition_id": composition_id, "role": "lead", "instrument": "Glass Lead", "volume": 0.44, "pan": 0.2},
    ).to_dict()
    assert created_track["ok"] is True
    track_id = created_track["result"]["track"]["id"]

    clip = registry.execute(
        "midi.clip.create",
        {"composition_id": composition_id, "track_id": track_id, "start_ms": 0, "duration_ms": 2000, "clip_id": "lead_a"},
    ).to_dict()
    assert clip["ok"] is True

    notes = registry.execute(
        "midi.clip.write_notes",
        {
            "composition_id": composition_id,
            "track_id": track_id,
            "clip_id": "lead_a",
            "notes": [
                {"pitch": 64, "start_tick": 17, "duration_tick": 233, "velocity": 80},
                {"pitch": 67, "start_tick": 244, "duration_tick": 240, "velocity": 72},
            ],
        },
    ).to_dict()
    assert notes["ok"] is True
    assert notes["result"]["note_count"] == 2

    quantized = registry.execute(
        "midi.clip.quantize",
        {"composition_id": composition_id, "track_id": track_id, "clip_id": "lead_a", "grid": "1/8"},
    ).to_dict()
    assert quantized["ok"] is True
    assert quantized["result"]["grid_ticks"] == 240

    chords = registry.execute(
        "midi.clip.write_chords",
        {
            "composition_id": composition_id,
            "track_id": track_id,
            "clip_id": "lead_a",
            "chords": ["Cm", "Ab"],
            "replace": True,
        },
    ).to_dict()
    assert chords["ok"] is True
    assert chords["result"]["note_count"] == 6

    regen = registry.execute(
        "music.regenerate_section",
        {"composition_id": composition_id, "section_name": "main", "intensity": 0.7},
    ).to_dict()
    assert regen["ok"] is True

    rendered = registry.execute(
        "music.render.preview",
        {"composition_id": composition_id, "output_dir": str(tmp_path)},
    ).to_dict()
    assert rendered["ok"] is True
    assert Path(rendered["result"]["preview_mix_path"]).exists()
