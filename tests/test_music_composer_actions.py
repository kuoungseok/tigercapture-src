from __future__ import annotations

import json
import subprocess
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
        "tigerstudio.sample_production.v1",
    }
    assert rendered["result"]["render_backend"]["backend"] in {"local_synth", "fluidsynth_soundfont", "studio_edm", "sample_production"}
    assert rendered["result"]["render_backend"]["quality_tier"] in {"diagnostic_only", "draft_sketch", "starter_preview", "enhanced_local_preview"}
    assert rendered["result"]["render_backend"]["production_ready"] is False

    local_rendered = registry.execute(
        "music.render.preview",
        {"composition_id": composition_id, "output_dir": str(tmp_path), "backend": "local_synth"},
    ).to_dict()
    assert local_rendered["ok"] is True
    assert local_rendered["result"]["render_engine"] == "tigerstudio.local_synth.v5"
    assert local_rendered["result"]["render_backend"]["backend"] == "local_synth"
    assert local_rendered["result"]["render_backend"]["quality_tier"] == "diagnostic_only"
    assert local_rendered["result"]["render_backend"]["production_ready"] is False

    backends = registry.execute("music.render.backends", {}).to_dict()
    assert backends["ok"] is True
    assert backends["result"]["preferred_backend"] == "sample_production"
    assert backends["result"]["basic_backend"] == "tigerstudio.sample_production.v1"
    assert backends["result"]["auto_policy"] == "sample_production_default; production_external_only_when_explicitly_requested"
    assert backends["result"]["default_studio_mastering"]["enabled"] is True
    assert backends["result"]["default_studio_mastering"]["profile"] == "one_click_sample_production_studio_v1"
    assert backends["result"]["default_performance_profile"]["enabled"] is True
    assert backends["result"]["default_performance_profile"]["profile"] == "sample_production_articulation_expression_v1"
    assert backends["result"]["quality_tiers"]["local_synth"] == "diagnostic_only"
    assert backends["result"]["quality_tiers"]["fluidsynth_soundfont"] == "starter_preview"
    assert backends["result"]["quality_tiers"]["production_external"] == "production_candidate"
    assert "quality_warning" in backends["result"]
    assert any("external" in path and "soundfonts" in path for path in backends["result"]["asset_dirs"])
    assert {row["value"] for row in backends["result"]["sample_library_choices"]} >= {
        "auto",
        "sample_kit_first",
        "soundfont_only",
        "procedural_only",
    }
    assert "recommended_sample_libraries" in backends["result"]
    assert "root" in backends["result"]["sample_library_install_dirs"]

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


def test_sample_production_backend_renders_bus_stems(tmp_path: Path) -> None:
    from app.music_composer import compose_music, render_preview

    composition = compose_music(
        prompt="original tactical stealth thriller cue with low strings and muted percussion",
        duration_ms=8000,
        genre="cinematic electronic stealth score",
        mood="tense covert tactical",
        bpm=92,
        key="D minor",
    )
    rendered = render_preview(composition, output_dir=tmp_path, backend="sample_production", render_stems=True)

    mix_path = Path(rendered["preview_mix_path"])
    assert rendered["render_engine"] == "tigerstudio.sample_production.v1"
    assert rendered["render_backend"]["backend"] == "sample_production"
    assert rendered["render_backend"]["quality_tier"] == "enhanced_local_preview"
    assert rendered["render_backend"]["stem_policy"] == "bus_stems"
    assert rendered["render_backend"]["studio_mastering"]["enabled"] is True
    assert rendered["render_backend"]["studio_mastering"]["profile"] == "one_click_sample_production_studio_v1"
    assert rendered["render_backend"]["studio_mastering"]["one_click_ai_default"] is True
    assert "mid-side stereo width" in rendered["render_backend"]["studio_mastering"]["chain"]
    assert rendered["render_backend"]["performance_profile"]["enabled"] is True
    assert rendered["render_backend"]["performance_profile"]["profile"] == "sample_production_articulation_expression_v1"
    assert rendered["render_backend"]["performance_profile"]["note_count"] > 0
    assert rendered["render_backend"]["performance_profile"]["articulation_counts"]
    assert mix_path.exists()
    assert mix_path.stat().st_size > 44
    assert rendered["stems"]
    assert set(rendered["stems"]) <= {"percussion", "low", "orchestra", "pads", "lead", "fx"}
    assert all(Path(path).exists() for path in rendered["stems"].values())
    assert rendered["render_backend"]["percussion_source"] in {"drum_sample_kit", "soundfont", "procedural_synth", "none"}


def test_sample_production_midi_export_includes_expression_performance_profile(tmp_path: Path) -> None:
    import app.music_composer as music_composer

    composition = music_composer.MusicComposition(
        id="expression_profile",
        prompt="orchestral strings performance test",
        genre="orchestral",
        mood="cinematic",
        bpm=96,
        key="D minor",
        duration_ms=4000,
        tracks=[
            music_composer.MusicTrack(
                id="violins_i_001",
                role="violins_i_001",
                instrument="Violins I",
                clips=[
                    music_composer.MidiClip(
                        id="clip",
                        section_name="main",
                        start_ms=0,
                        duration_ms=4000,
                        notes=[
                            music_composer.MidiNote(72, 0, int(music_composer.TICKS_PER_BEAT * 0.25), 92),
                            music_composer.MidiNote(76, music_composer.TICKS_PER_BEAT, int(music_composer.TICKS_PER_BEAT * 2.5), 88),
                        ],
                    )
                ],
            )
        ],
    )

    midi = music_composer.export_midi(composition, output_dir=tmp_path)
    payload = Path(midi["path"]).read_bytes()

    assert midi["performance_profile"]["enabled"] is True
    assert midi["performance_profile"]["articulation_counts"]["spiccato"] == 1
    assert midi["performance_profile"]["articulation_counts"]["sustain"] == 1
    assert payload.count(bytes((0xB0, 11))) >= 3
    assert bytes((0xB0, 1)) in payload


def test_sample_production_uses_soundfont_percussion_bus_when_available(tmp_path: Path, monkeypatch) -> None:
    import numpy as np
    import app.music_composer as music_composer

    composition = music_composer.compose_music(
        prompt="original creator music with punchy sampled drums",
        duration_ms=5000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    calls: list[list[str]] = []

    def fake_soundfont_bus_samples(comp, tracks, *, output_dir, suffix, target_length, soundfont_path=None):
        calls.append([track.role for track in tracks])
        samples = np.zeros((target_length, 2), dtype=np.float32)
        start = int(0.5 * music_composer.SAMPLE_RATE)
        stop = start + int(0.08 * music_composer.SAMPLE_RATE)
        samples[start:stop, :] = 0.08
        return samples, {
            "source": "soundfont",
            "ready": True,
            "soundfont_path": "external/assets/music/soundfonts/test.sf2",
            "fluidsynth_path": "external/tools/fluidsynth/bin/fluidsynth.exe",
        }

    monkeypatch.setattr(music_composer, "music_drum_kit_dirs", lambda: [tmp_path / "empty_drum_kits"])
    monkeypatch.setattr(music_composer, "_render_soundfont_bus_samples", fake_soundfont_bus_samples)

    rendered = music_composer.render_preview(
        composition,
        output_dir=tmp_path,
        backend="sample_production",
        render_stems=False,
    )

    assert calls
    assert "drums" in calls[0]
    assert rendered["render_backend"]["percussion_source"] == "soundfont"
    assert rendered["render_backend"]["percussion_renderer"]["ready"] is True
    assert "SoundFont/FluidSynth" in rendered["render_backend"]["quality_warning"]
    assert rendered["render_backend"]["external_bus_count"] >= 1
    assert rendered["render_backend"]["bus_renderers"]["percussion"]["source"] == "soundfont"


def test_sample_production_soundfont_only_skips_drum_sample_kit(tmp_path: Path, monkeypatch) -> None:
    import numpy as np
    import app.music_composer as music_composer

    composition = music_composer.compose_music(
        prompt="original creator music with sampled drums",
        duration_ms=5000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    kit_calls: list[str] = []
    soundfont_calls: list[str] = []

    def fake_kit(*args, **kwargs):
        kit_calls.append("called")
        return None, {"source": "soundfont", "ready": False, "reason": "should be skipped"}

    def fake_soundfont(_comp, tracks, *, output_dir, suffix, target_length, soundfont_path=None):
        soundfont_calls.extend(track.role for track in tracks)
        samples = np.zeros((target_length, 2), dtype=np.float32)
        samples[: min(target_length, 128), :] = 0.05
        return samples, {"source": "soundfont", "ready": True, "soundfont_path": str(soundfont_path or "test.sf2")}

    monkeypatch.setattr(music_composer, "_render_sample_kit_bus_samples", fake_kit)
    monkeypatch.setattr(music_composer, "_render_soundfont_bus_samples", fake_soundfont)

    rendered = music_composer.render_preview(
        composition,
        output_dir=tmp_path,
        backend="sample_production",
        sample_library_policy="soundfont_only",
        soundfont_path="external/assets/music/soundfonts/test.sf2",
        render_stems=False,
    )

    assert kit_calls == []
    assert soundfont_calls
    assert rendered["render_backend"]["sample_library_policy"] == "soundfont_only"
    assert rendered["render_backend"]["percussion_source"] == "soundfont"


def test_sample_production_procedural_only_skips_external_libraries(tmp_path: Path, monkeypatch) -> None:
    import app.music_composer as music_composer

    composition = music_composer.compose_music(
        prompt="original creator music internal synth comparison",
        duration_ms=5000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    calls: list[str] = []
    monkeypatch.setattr(music_composer, "_render_sample_kit_bus_samples", lambda *args, **kwargs: calls.append("kit"))
    monkeypatch.setattr(music_composer, "_render_soundfont_bus_samples", lambda *args, **kwargs: calls.append("soundfont"))

    rendered = music_composer.render_preview(
        composition,
        output_dir=tmp_path,
        backend="sample_production",
        sample_library_policy="procedural_only",
        render_stems=False,
    )

    assert calls == []
    assert rendered["render_backend"]["sample_library_policy"] == "procedural_only"
    assert rendered["render_backend"]["percussion_source"] == "procedural_synth"


def test_sample_production_prefers_sfz_drum_sample_kit(tmp_path: Path, monkeypatch) -> None:
    import math
    import wave
    import numpy as np
    import app.music_composer as music_composer

    kit_dir = tmp_path / "kit"
    samples_dir = kit_dir / "Samples"
    samples_dir.mkdir(parents=True)
    wav_path = samples_dir / "kick.wav"
    sample_rate = music_composer.SAMPLE_RATE
    length = int(sample_rate * 0.18)
    t = np.arange(length, dtype=np.float32) / float(sample_rate)
    tone = np.sin(2.0 * math.pi * 72.0 * t) * np.exp(-t * 18.0) * 0.35
    data = (np.clip(np.stack([tone, tone], axis=1), -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(data.tobytes())
    sfz_path = kit_dir / "test_drumkit.sfz"
    sfz_path.write_text("<group>\n<region> sample=Samples/kick.wav key=36 lovel=1 hivel=127\n", encoding="utf-8")

    composition = music_composer.compose_music(
        prompt="original creator music with acoustic sampled drums",
        duration_ms=5000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )

    monkeypatch.setattr(music_composer, "music_drum_kit_dirs", lambda: [kit_dir])
    monkeypatch.setattr(
        music_composer,
        "_render_soundfont_bus_samples",
        lambda *args, **kwargs: (None, {"source": "procedural_synth", "ready": False, "reason": "disabled in test"}),
    )

    rendered = music_composer.render_preview(
        composition,
        output_dir=tmp_path,
        backend="sample_production",
        render_stems=False,
    )

    percussion = rendered["render_backend"]["percussion_renderer"]
    assert rendered["render_backend"]["percussion_source"] == "drum_sample_kit"
    assert percussion["kit_path"] == str(sfz_path)
    assert percussion["samples_used"] == 1
    assert rendered["render_backend"]["bus_renderers"]["percussion"]["source"] == "drum_sample_kit"


def test_sample_production_maps_metal_guitar_roles_to_soundfont_guitars() -> None:
    import app.music_composer as music_composer

    assert music_composer._role_family("rhythm_guitar_001") == "guitar"
    assert music_composer._role_family("lead_guitar_001") == "guitar"
    assert music_composer._sample_production_bus_for_role("rhythm_guitar_001") == "lead"
    assert music_composer._midi_program_for_role("rhythm_guitar_001") == 30
    assert music_composer._midi_program_for_role("lead_guitar_001") == 29


def test_sample_production_repairs_short_energy_dips() -> None:
    import numpy as np

    from app.music_composer import SAMPLE_RATE, _repair_short_energy_dips

    length = SAMPLE_RATE * 2
    t = np.arange(length, dtype=np.float32) / float(SAMPLE_RATE)
    samples = np.stack(
        [
            np.sin(2.0 * np.pi * 220.0 * t) * 0.08,
            np.sin(2.0 * np.pi * 222.0 * t) * 0.08,
        ],
        axis=1,
    ).astype(np.float32)
    start = int(round(0.45 * SAMPLE_RATE))
    stop = start + int(round(0.05 * SAMPLE_RATE))
    samples[start:stop] *= 0.12

    def dropout_count(arr) -> int:
        win = int(SAMPLE_RATE * 0.05)
        rms = np.array([np.sqrt(np.mean(arr[i:i + win] ** 2)) for i in range(0, len(arr) - win, win)])
        count = 0
        for idx in range(1, len(rms) - 1):
            neighbor = (rms[idx - 1] + rms[idx + 1]) / 2.0
            if neighbor > 0.015 and rms[idx] < neighbor * 0.18:
                count += 1
        return count

    assert dropout_count(samples) >= 1
    _repair_short_energy_dips(samples, window_ms=50.0, floor_ratio=0.42, max_gain=3.0)
    assert dropout_count(samples) == 0


def test_sample_production_repairs_isolated_frame_dropouts() -> None:
    import numpy as np

    from app.music_composer import SAMPLE_RATE, _repair_isolated_frame_dropouts

    length = SAMPLE_RATE * 2
    t = np.arange(length, dtype=np.float32) / float(SAMPLE_RATE)
    base = np.sin(2.0 * np.pi * 220.0 * t) * 0.065
    samples = np.stack([base, base], axis=1).astype(np.float32)
    window = int(round(SAMPLE_RATE * 0.025))
    start = int(round(0.80 * SAMPLE_RATE))
    stop = start + window
    samples[start:stop] *= 0.05

    def frame_ratio(arr) -> float:
        current = float(np.sqrt(np.mean(arr[start:stop] ** 2)))
        before = float(np.sqrt(np.mean(arr[start - window:start] ** 2)))
        after = float(np.sqrt(np.mean(arr[stop:stop + window] ** 2)))
        return current / max((before + after) * 0.5, 0.000001)

    before = frame_ratio(samples)
    _repair_isolated_frame_dropouts(samples, window_ms=25.0, floor_ratio=0.44, max_gain=2.15)
    after = frame_ratio(samples)

    assert before < 0.08
    assert after > before * 1.8


def test_sample_production_smooths_clicky_sample_jumps() -> None:
    import numpy as np

    from app.music_composer import SAMPLE_RATE, _smooth_sample_jumps

    length = SAMPLE_RATE
    t = np.arange(length, dtype=np.float32) / float(SAMPLE_RATE)
    samples = np.stack(
        [
            np.sin(2.0 * np.pi * 180.0 * t) * 0.08,
            np.sin(2.0 * np.pi * 183.0 * t) * 0.08,
        ],
        axis=1,
    ).astype(np.float32)
    click = int(round(0.5 * SAMPLE_RATE))
    samples[click] += np.array([0.42, -0.39], dtype=np.float32)

    before = float(np.max(np.max(np.abs(np.diff(samples, axis=0)), axis=1)))
    _smooth_sample_jumps(samples, threshold=0.12, radius=5, passes=2)
    after = float(np.max(np.max(np.abs(np.diff(samples, axis=0)), axis=1)))

    assert before > 0.30
    assert after <= 0.12


def test_sample_production_tames_low_resonance() -> None:
    import numpy as np

    from app.music_composer import SAMPLE_RATE, _tame_low_resonance

    length = SAMPLE_RATE * 2
    t = np.arange(length, dtype=np.float32) / float(SAMPLE_RATE)
    tone = np.sin(2.0 * np.pi * 65.0 * t) * 0.16
    bed = np.sin(2.0 * np.pi * 220.0 * t) * 0.025
    samples = np.stack([tone + bed, tone + bed * 0.95], axis=1).astype(np.float32)

    def low_peak(arr) -> float:
        frame = SAMPLE_RATE
        mono = np.mean(arr[:frame], axis=1)
        spec = np.abs(np.fft.rfft(mono * np.hanning(frame)))
        freqs = np.fft.rfftfreq(frame, 1.0 / SAMPLE_RATE)
        mask = (freqs >= 28.0) & (freqs <= 120.0)
        return float(np.max(spec[mask]))

    before = low_peak(samples)
    _tame_low_resonance(samples, ratio_threshold=40.0)
    after = low_peak(samples)

    assert before > 1000.0
    assert after < before * 0.55


def test_sample_production_tames_tonal_whine() -> None:
    import numpy as np

    from app.music_composer import SAMPLE_RATE, _tame_tonal_whine

    length = SAMPLE_RATE
    t = np.arange(length, dtype=np.float32) / float(SAMPLE_RATE)
    whine = np.sin(2.0 * np.pi * 2093.0 * t) * 0.075
    bed = np.sin(2.0 * np.pi * 330.0 * t) * 0.025
    samples = np.stack([whine + bed, whine * 0.98 + bed], axis=1).astype(np.float32)

    def whine_peak(arr) -> float:
        frame = SAMPLE_RATE
        mono = np.mean(arr[:frame], axis=1)
        spec = np.abs(np.fft.rfft(mono * np.hanning(frame)))
        freqs = np.fft.rfftfreq(frame, 1.0 / SAMPLE_RATE)
        mask = (freqs >= 1600.0) & (freqs <= 2600.0)
        return float(np.max(spec[mask]))

    before = whine_peak(samples)
    _tame_tonal_whine(samples)
    after = whine_peak(samples)

    assert before > 300.0
    assert after < before * 0.55


def test_sample_production_softens_short_energy_surges() -> None:
    import numpy as np

    from app.music_composer import SAMPLE_RATE, _soften_short_energy_surges

    length = SAMPLE_RATE
    t = np.arange(length, dtype=np.float32) / float(SAMPLE_RATE)
    base = np.sin(2.0 * np.pi * 220.0 * t) * 0.045
    samples = np.stack([base, base], axis=1).astype(np.float32)
    start = int(round(0.50 * SAMPLE_RATE))
    stop = start + int(round(0.010 * SAMPLE_RATE))
    samples[start:stop] *= 5.5

    def frame_rms(arr) -> float:
        return float(np.sqrt(np.mean(arr[start:stop] ** 2)))

    before = frame_rms(samples)
    _soften_short_energy_surges(samples, window_ms=10.0, ceiling_ratio=2.15, max_reduction=0.72)
    after = frame_rms(samples)

    assert before > 0.12
    assert after < before * 0.86


def test_auto_preview_uses_sample_production_before_soundfont_or_draft_edm(tmp_path: Path, monkeypatch) -> None:
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

    def fake_sample_production_preview(*args, **kwargs):
        calls.append("sample_production")
        composition.render_engine = "tigerstudio.sample_production.v1"
        composition.render_backend = {
            "backend": "sample_production",
            "quality_tier": "enhanced_local_preview",
            "production_ready": False,
        }
        mix_path = tmp_path / "auto_sample_production.wav"
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
    monkeypatch.setattr(music_composer, "_render_sample_production_preview", fake_sample_production_preview)
    monkeypatch.setattr(music_composer, "_render_soundfont_preview", fake_soundfont_preview)
    monkeypatch.setattr(music_composer, "_render_studio_edm_preview", fail_studio)

    rendered = music_composer.render_preview(composition, output_dir=tmp_path, backend="auto", render_stems=False)

    assert calls == ["sample_production"]
    assert rendered["render_backend"]["backend"] == "sample_production"


def test_auto_mix_only_preview_keeps_sample_production_even_when_ai_renderer_is_configured(tmp_path: Path, monkeypatch) -> None:
    import app.music_composer as music_composer

    composition = music_composer.compose_music(
        prompt="modern EDM production preview",
        duration_ms=8000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    calls: list[str] = []

    def fake_sample_production_preview(*args, **kwargs):
        calls.append("sample_production")
        composition.render_engine = "tigerstudio.sample_production.v1"
        composition.render_backend = {
            "backend": "sample_production",
            "quality_tier": "enhanced_local_preview",
            "production_ready": False,
            "render_stems": False,
        }
        mix_path = tmp_path / "sample_production.wav"
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

    def fake_production_preview(*args, **kwargs):
        calls.append("production_external")
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
    monkeypatch.setattr(music_composer, "_render_sample_production_preview", fake_sample_production_preview)
    monkeypatch.setattr(music_composer, "_render_external_production_preview", fake_production_preview)

    rendered = music_composer.render_preview(composition, output_dir=tmp_path, backend="auto", render_stems=False)

    assert calls == ["sample_production"]
    assert rendered["render_backend"]["backend"] == "sample_production"
    assert rendered["render_backend"]["quality_tier"] == "enhanced_local_preview"

    explicit = music_composer.render_preview(composition, output_dir=tmp_path, backend="production", render_stems=False)

    assert calls[-1] == "production_external"
    assert explicit["render_backend"]["backend"] == "production_external"
    assert explicit["render_backend"]["quality_tier"] == "production_candidate"


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


def test_production_preview_passes_selected_ai_provider(tmp_path: Path, monkeypatch) -> None:
    import app.music_composer as music_composer

    composition = music_composer.compose_music(
        prompt="stable audio release cue",
        duration_ms=8000,
        genre="melodic EDM",
        mood="uplifting",
        bpm=128,
        key="A minor",
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        music_composer,
        "music_production_renderer_status",
        lambda: {
            "backend": "production_external",
            "ready": True,
            "configured": True,
            "command": ["renderer"],
            "supports_stems": False,
            "quality_tier": "production_candidate",
            "source": "test",
        },
    )

    def fake_run(command, *, cwd, capture_output, text, env, timeout, check):
        captured["command"] = list(command)
        captured["env_provider"] = dict(env).get("TIGERCAPTURE_MUSIC_AI_PROVIDER")
        request_path = Path(command[command.index("--composition-json") + 1])
        output_path = Path(command[command.index("--output-wav") + 1])
        captured["request"] = json.loads(request_path.read_text(encoding="utf-8"))
        output_path.write_bytes(b"RIFF" + (b"\x00" * 80) + b"WAVE")
        output_path.with_suffix(output_path.suffix + ".renderer.json").write_text(
            json.dumps(
                {
                    "provider": "stable_audio_3",
                    "provider_engine": "Stable Audio 3.0 HF Space/small-music",
                    "fallback_used": False,
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(music_composer.subprocess, "run", fake_run)

    rendered = music_composer.render_preview(
        composition,
        output_dir=tmp_path,
        backend="production",
        ai_provider="stable_audio_3",
        render_stems=False,
    )

    assert captured["env_provider"] == "stable_audio_3"
    assert captured["request"]["ai_provider"] == "stable_audio_3"
    assert rendered["render_backend"]["provider"] == "stable_audio_3"
    assert rendered["render_backend"]["requested_ai_provider"] == "stable_audio_3"


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


def test_melodic_edm_bass_avoids_short_end_beat_stutters() -> None:
    from app.music_composer import TICKS_PER_BEAT, _role_tail_seconds, compose_music

    composition = compose_music(
        prompt="original NCS style melodic EDM hook with smoother low end",
        duration_ms=30000,
        genre="melodic EDM",
        mood="bright",
        bpm=128,
        key="A minor",
    )
    bass = next(track for track in composition.tracks if track.role == "bass")
    pulse = next(track for track in composition.tracks if track.role == "bass_pulse")
    bass_notes = [note for clip in bass.clips for note in clip.notes]
    pulse_notes = [note for clip in pulse.clips for note in clip.notes]

    assert bass_notes
    assert pulse_notes
    assert min(note.duration_tick for note in bass_notes) >= int(TICKS_PER_BEAT * 0.60)
    assert min(note.duration_tick for note in pulse_notes) >= int(TICKS_PER_BEAT * 0.56)
    assert all((note.start_tick % (TICKS_PER_BEAT * 4)) < int(TICKS_PER_BEAT * 3.40) for note in pulse_notes)
    assert _role_tail_seconds("bass", bass_notes[0]) >= 0.20
    assert _role_tail_seconds("bass_pulse", pulse_notes[0]) >= 0.14


def test_melodic_phrase_planner_uses_song_form_labels() -> None:
    import math

    from app.music_composer import _melody_phrase_plans_for_section, compose_music

    composition = compose_music(
        prompt="original NCS style melodic EDM hook with bridge and second drop",
        duration_ms=60000,
        genre="melodic EDM",
        mood="bright",
        bpm=128,
        key="A minor",
    )
    labels: list[str] = []
    planned_bars: list[int] = []
    phrase_cursor = 0
    bar_ms = 60000.0 / composition.bpm * 4.0
    for section in composition.sections:
        bars = max(1, int(math.ceil(section.duration_ms / max(1.0, bar_ms))))
        plans = _melody_phrase_plans_for_section(section, bars=bars, phrase_index_start=phrase_cursor)
        labels.extend(plan.label for plan in plans)
        planned_bars.extend(plan.bars for plan in plans)
        phrase_cursor += len(plans)

    assert {"A", "A_prime", "B", "hook", "bridge"} <= set(labels)
    assert any(bars in {8, 16} for bars in planned_bars)


def test_melodic_phrase_generation_avoids_short_loop_repetition() -> None:
    from app.music_composer import TICKS_PER_BEAT, compose_music

    composition = compose_music(
        prompt="original NCS style melodic EDM hook with long evolving lead",
        duration_ms=60000,
        genre="melodic EDM",
        mood="bright",
        bpm=128,
        key="A minor",
    )
    melody = next(track for track in composition.tracks if track.role == "melody")
    answer = next(track for track in composition.tracks if track.role == "lead_answer")
    counter = next(track for track in composition.tracks if track.role == "counter")
    notes = sorted([note for clip in melody.clips for note in clip.notes], key=lambda note: note.start_tick)
    assert len(notes) >= 80

    bar_ticks = TICKS_PER_BEAT * 4
    phrase_signatures: list[tuple[tuple[float, int, float], ...]] = []
    total_bars = max(1, int(round(composition.duration_ms * composition.bpm / 60000.0 / 4.0)))
    for chunk_start_bar in range(0, total_bars, 4):
        start = chunk_start_bar * bar_ticks
        stop = start + bar_ticks * 4
        signature = tuple(
            (
                round((note.start_tick - start) / TICKS_PER_BEAT, 2),
                int(note.pitch),
                round(note.duration_tick / TICKS_PER_BEAT, 2),
            )
            for note in notes
            if start <= note.start_tick < stop
        )[:16]
        if signature:
            phrase_signatures.append(signature)

    assert len(phrase_signatures) >= 6
    assert len(set(phrase_signatures)) >= min(len(phrase_signatures), 6)
    assert all(left != right for left, right in zip(phrase_signatures, phrase_signatures[1:]))
    assert sum(len(clip.notes) for clip in answer.clips) > 0
    assert sum(len(clip.notes) for clip in counter.clips) > 0
    assert sum(len(clip.notes) for clip in answer.clips) < len(notes)
    assert sum(len(clip.notes) for clip in counter.clips) < len(notes)


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
