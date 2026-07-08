"""MIDI-first AI Composer model, generator, and local preview renderer."""
from __future__ import annotations

import hashlib
import json
import math
import os
import shlex
import shutil
import struct
import subprocess
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


TICKS_PER_BEAT = 480
SAMPLE_RATE = 44100
MUSIC_SCHEMA = "tigerstudio.music.composition.v1"
DEFAULT_MUSIC_TRACK_COUNT = 9
ORCHESTRAL_TRACK_COUNT = 128
MUSIC_QUALITY_DRAFT = "draft_sketch"
MUSIC_QUALITY_STARTER = "starter_preview"
MUSIC_QUALITY_PRODUCTION = "production_candidate"


@dataclass
class MidiNote:
    pitch: int
    start_tick: int
    duration_tick: int
    velocity: int = 90


@dataclass
class MidiClip:
    id: str
    section_name: str
    start_ms: int
    duration_ms: int
    notes: list[MidiNote] = field(default_factory=list)


@dataclass
class MusicTrack:
    id: str
    role: str
    instrument: str
    volume: float = 0.8
    pan: float = 0.0
    clips: list[MidiClip] = field(default_factory=list)


@dataclass
class MusicSection:
    name: str
    start_ms: int
    duration_ms: int
    intensity: float
    chord_progression: list[str] = field(default_factory=list)


@dataclass
class MusicComposition:
    id: str
    prompt: str
    genre: str
    mood: str
    bpm: int
    key: str
    duration_ms: int
    ticks_per_beat: int = TICKS_PER_BEAT
    sections: list[MusicSection] = field(default_factory=list)
    tracks: list[MusicTrack] = field(default_factory=list)
    rendered_stems: dict[str, str] = field(default_factory=dict)
    preview_mix_path: str = ""
    render_engine: str = ""
    render_backend: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["schema"] = MUSIC_SCHEMA
        return row


def composition_from_dict(row: dict[str, Any]) -> MusicComposition:
    sections = [MusicSection(**section) for section in list(row.get("sections") or [])]
    tracks: list[MusicTrack] = []
    for track in list(row.get("tracks") or []):
        clips: list[MidiClip] = []
        for clip in list(track.get("clips") or []):
            notes = [MidiNote(**note) for note in list(clip.get("notes") or [])]
            clip_row = dict(clip)
            clip_row["notes"] = notes
            clips.append(MidiClip(**clip_row))
        track_row = dict(track)
        track_row["clips"] = clips
        tracks.append(MusicTrack(**track_row))
    return MusicComposition(
        id=str(row.get("id") or ""),
        prompt=str(row.get("prompt") or ""),
        genre=str(row.get("genre") or ""),
        mood=str(row.get("mood") or ""),
        bpm=int(row.get("bpm") or 100),
        key=str(row.get("key") or "C minor"),
        duration_ms=int(row.get("duration_ms") or 30000),
        ticks_per_beat=int(row.get("ticks_per_beat") or TICKS_PER_BEAT),
        sections=sections,
        tracks=tracks,
        rendered_stems=dict(row.get("rendered_stems") or {}),
        preview_mix_path=str(row.get("preview_mix_path") or ""),
        render_engine=str(row.get("render_engine") or ""),
        render_backend=dict(row.get("render_backend") or {}),
    )


def composition_id(prompt: str, duration_ms: int, genre: str, mood: str, bpm: int, key: str) -> str:
    payload = json.dumps(
        {
            "prompt": prompt,
            "duration_ms": int(duration_ms),
            "genre": genre,
            "mood": mood,
            "bpm": int(bpm),
            "key": key,
        },
        sort_keys=True,
    )
    return "music_" + hashlib.sha1(payload.encode("utf-8", errors="replace")).hexdigest()[:12]


def _clean_text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").strip().split())
    return text or fallback


def _is_orchestral_request(prompt: str = "", genre: str = "", mood: str = "") -> bool:
    text = f"{prompt} {genre} {mood}".lower()
    compact = "".join(text.split())
    direct = (
        "orchestra",
        "orchestral",
        "symphonic",
        "symphony",
        "film score",
        "trailer score",
        "cinematic score",
    )
    localized = (
        "\uc624\ucf00\uc2a4\ud2b8\ub77c",
        "\uad00\ud604\uc545",
        "\uc2ec\ud3ec\ub2c9",
    )
    if any(marker in text for marker in direct) or any(marker in compact for marker in localized):
        return True
    return "trailer" in text and any(word in text for word in ("epic", "cinematic", "score"))


def _is_melodic_edm_request(prompt: str = "", genre: str = "", mood: str = "") -> bool:
    text = f"{prompt} {genre} {mood}".lower()
    markers = (
        "ncs",
        "alan walker",
        "melodic edm",
        "edm",
        "electronic",
        "dance",
        "future bass",
        "progressive house",
    )
    return any(marker in text for marker in markers)


def choose_bpm(prompt: str = "", genre: str = "", mood: str = "", bpm: int | None = None) -> int:
    if bpm:
        return max(48, min(180, int(bpm)))
    if _is_orchestral_request(prompt, genre, mood):
        return 92
    text = f"{prompt} {genre} {mood}".lower()
    if any(word in text for word in ("techno", "edm", "electronic", "dance", "driving")):
        return 124
    if any(word in text for word in ("lofi", "lo-fi", "chill", "relax")):
        return 82
    if any(word in text for word in ("trailer", "epic", "cinematic")):
        return 96
    if any(word in text for word in ("corporate", "tutorial", "explain")):
        return 108
    return 112


def choose_key(prompt: str = "", mood: str = "", key: str = "") -> str:
    if _clean_text(key):
        return _clean_text(key)
    text = f"{prompt} {mood}".lower()
    if any(word in text for word in ("bright", "happy", "uplift", "corporate")):
        return "C major"
    if any(word in text for word in ("dark", "tense", "trailer", "cinematic")):
        return "D minor"
    return "C minor"


def _is_minor(key: str) -> bool:
    return "minor" in str(key or "").lower() or str(key or "").strip().endswith("m")


def _root_pitch_for_key(key: str) -> int:
    name = str(key or "C").strip().split()[0].replace("m", "")
    roots = {
        "C": 48,
        "C#": 49,
        "Db": 49,
        "D": 50,
        "D#": 51,
        "Eb": 51,
        "E": 52,
        "F": 53,
        "F#": 54,
        "Gb": 54,
        "G": 55,
        "G#": 56,
        "Ab": 56,
        "A": 57,
        "A#": 58,
        "Bb": 58,
        "B": 59,
    }
    return roots.get(name, 48)


_NOTE_TO_INDEX = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}
_FLAT_NOTE_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def _key_root_name(key: str) -> str:
    raw = str(key or "C").strip().split()[0].replace("m", "")
    if raw in _NOTE_TO_INDEX:
        return _FLAT_NOTE_NAMES[_NOTE_TO_INDEX[raw]]
    return "C"


def _transpose_chord(root: str, semitones: int, *, minor: bool = False) -> str:
    index = (_NOTE_TO_INDEX.get(root, 0) + int(semitones)) % 12
    name = _FLAT_NOTE_NAMES[index]
    return f"{name}m" if minor else name


def chord_progression_for(key: str, genre: str = "", mood: str = "") -> list[str]:
    root = _key_root_name(key)
    text = f"{genre} {mood}".lower()
    if _is_minor(key):
        return [
            _transpose_chord(root, 0, minor=True),
            _transpose_chord(root, 8),
            _transpose_chord(root, 3),
            _transpose_chord(root, 10),
        ]
    if "lofi" in text or "chill" in text:
        return [
            _transpose_chord(root, 0),
            _transpose_chord(root, 4, minor=True),
            _transpose_chord(root, 9, minor=True),
            _transpose_chord(root, 5),
        ]
    return [
        _transpose_chord(root, 0),
        _transpose_chord(root, 9, minor=True),
        _transpose_chord(root, 5),
        _transpose_chord(root, 7),
    ]


def _sections(duration_ms: int, chords: list[str]) -> list[MusicSection]:
    duration = max(4000, int(duration_ms or 30000))
    if duration <= 16000:
        ratios = (("intro", 0.25, 0.45), ("main", 0.55, 0.92), ("outro", 0.20, 0.35))
    else:
        ratios = (("intro", 0.18, 0.42), ("build", 0.27, 0.68), ("main", 0.38, 0.95), ("outro", 0.17, 0.38))
    start = 0
    rows: list[MusicSection] = []
    for index, (name, ratio, intensity) in enumerate(ratios):
        if index == len(ratios) - 1:
            section_duration = max(1, duration - start)
        else:
            section_duration = max(1, int(round(duration * ratio)))
        rows.append(MusicSection(name=name, start_ms=start, duration_ms=section_duration, intensity=float(intensity), chord_progression=list(chords)))
        start += section_duration
    return rows


def _edm_progressions_for_key(key: str) -> dict[str, list[str]]:
    root = _key_root_name(key)
    if _is_minor(key):
        return {
            "base": [
                _transpose_chord(root, 0, minor=True),
                _transpose_chord(root, 8),
                _transpose_chord(root, 3),
                _transpose_chord(root, 10),
            ],
            "break": [
                _transpose_chord(root, 8),
                _transpose_chord(root, 10),
                _transpose_chord(root, 0, minor=True),
                _transpose_chord(root, 7, minor=True),
            ],
            "drop_alt": [
                _transpose_chord(root, 3),
                _transpose_chord(root, 10),
                _transpose_chord(root, 0, minor=True),
                _transpose_chord(root, 8),
            ],
        }
    return {
        "base": [
            _transpose_chord(root, 0),
            _transpose_chord(root, 9, minor=True),
            _transpose_chord(root, 5),
            _transpose_chord(root, 7),
        ],
        "break": [
            _transpose_chord(root, 5),
            _transpose_chord(root, 7),
            _transpose_chord(root, 0),
            _transpose_chord(root, 4, minor=True),
        ],
        "drop_alt": [
            _transpose_chord(root, 0),
            _transpose_chord(root, 7),
            _transpose_chord(root, 9, minor=True),
            _transpose_chord(root, 5),
        ],
    }


def _edm_sections(duration_ms: int, key: str, bpm: int) -> list[MusicSection]:
    duration = max(4000, int(duration_ms or 30000))
    progressions = _edm_progressions_for_key(key)
    bar_ms = 60000.0 / max(1, int(bpm or 120)) * 4.0
    requested_bars = max(1, int(math.ceil(duration / max(1.0, bar_ms))))
    if requested_bars >= 20:
        plan = (
            ("intro", 4, 0.34, "base"),
            ("build", 4, 0.70, "base"),
            ("drop_1", max(4, requested_bars - 16), 0.94, "base"),
            ("breakdown", 4, 0.46, "break"),
            ("drop_2_outro", 4, 0.88, "drop_alt"),
        )
    elif requested_bars >= 8:
        intro_bars = min(4, max(2, requested_bars // 4))
        build_bars = min(4, max(2, requested_bars // 4))
        breakdown_bars = 2 if requested_bars >= 12 else 1
        drop_bars = max(1, requested_bars - intro_bars - build_bars - breakdown_bars)
        plan = (
            ("intro", intro_bars, 0.36, "base"),
            ("build", build_bars, 0.66, "base"),
            ("drop_1", drop_bars, 0.92, "base"),
            ("breakdown", breakdown_bars, 0.44, "break"),
        )
    else:
        intro_bars = 1
        outro_bars = 1 if requested_bars >= 4 else 0
        drop_bars = max(1, requested_bars - intro_bars - outro_bars)
        plan_rows = [
            ("intro", intro_bars, 0.38, "base"),
            ("drop", drop_bars, 0.88, "base"),
        ]
        if outro_bars:
            plan_rows.append(("outro", outro_bars, 0.34, "drop_alt"))
        plan = tuple(plan_rows)
    rows: list[MusicSection] = []
    start_bars = 0
    for name, section_bars, intensity, progression_key in plan:
        start = int(round(start_bars * bar_ms))
        end = int(round((start_bars + section_bars) * bar_ms))
        section_duration = max(1, end - start)
        rows.append(
            MusicSection(
                name=name,
                start_ms=start,
                duration_ms=section_duration,
                intensity=float(intensity),
                chord_progression=list(progressions[progression_key]),
            )
        )
        start_bars += section_bars
    return rows


def _ms_to_tick(ms: int, bpm: int) -> int:
    beats = max(0.0, float(ms) * float(bpm) / 60000.0)
    return int(round(beats * TICKS_PER_BEAT))


def _trim_clip_notes_to_section(clip: MidiClip, *, section_start_tick: int, section_end_tick: int) -> None:
    trimmed: list[MidiNote] = []
    for note in clip.notes:
        start = max(0, int(note.start_tick))
        if start < section_start_tick:
            start = section_start_tick
        if start >= section_end_tick:
            continue
        duration = max(1, min(int(note.duration_tick), section_end_tick - start))
        trimmed.append(
            MidiNote(
                pitch=int(note.pitch),
                start_tick=start,
                duration_tick=duration,
                velocity=int(note.velocity),
            )
        )
    clip.notes = trimmed


def _chord_root(chord: str, key: str) -> int:
    text = str(chord or "").strip()
    if not text:
        return _root_pitch_for_key(key)
    name = text.replace("maj", "").replace("m", "")
    roots = {
        "C": 48,
        "C#": 49,
        "Db": 49,
        "D": 50,
        "D#": 51,
        "Eb": 51,
        "E": 52,
        "F": 53,
        "F#": 54,
        "Gb": 54,
        "G": 55,
        "G#": 56,
        "Ab": 56,
        "A": 57,
        "A#": 58,
        "Bb": 58,
        "B": 59,
    }
    return roots.get(name, _root_pitch_for_key(key))


def _chord_notes(chord: str, key: str, octave: int = 0) -> list[int]:
    root = _chord_root(chord, key) + octave * 12
    minor = str(chord or "").strip().endswith("m")
    third = 3 if minor else 4
    return [root, root + third, root + 7]


def _chord_voicing(chord: str, key: str, *, role: str = "pad") -> list[int]:
    root = _chord_root(chord, key)
    minor = str(chord or "").strip().endswith("m")
    third = 3 if minor else 4
    if role == "pad":
        return [root + 12, root + 19, root + 24 + third, root + 31, root + 36 + (10 if minor else 11)]
    return [root, root + third, root + 7]


def chord_notes(chord: str, key: str, octave: int = 0) -> list[int]:
    """Return MIDI pitches for a simple triad in the composition key."""
    return _chord_notes(chord, key, octave=octave)


def ms_to_tick(ms: int, bpm: int) -> int:
    """Return the composition tick position for an absolute project time."""
    return _ms_to_tick(ms, bpm)


def _clip_id(role: str, section_name: str) -> str:
    return f"{role}_{section_name}"


def _track(role: str, instrument: str, volume: float, pan: float) -> MusicTrack:
    return MusicTrack(id=role, role=role, instrument=instrument, volume=volume, pan=pan)


def _role_index(role: str) -> int:
    tail = str(role or "").rsplit("_", 1)[-1]
    try:
        return max(1, int(tail))
    except (TypeError, ValueError):
        return 1


def _role_family(role: str) -> str:
    text = str(role or "").lower()
    if text in {"drums", "bass", "chords", "pad", "melody", "fx", "lead"}:
        return text
    if text.startswith(("violins_i_", "violins_ii_")):
        return "strings_high"
    if text.startswith("violas_"):
        return "strings_mid"
    if text.startswith(("cellos_", "contrabasses_")):
        return "strings_low"
    if text in {"bass_pulse", "bass_layer", "sub_bass"} or text.startswith(("bass_pulse_", "bass_layer_", "sub_bass_")):
        return "bass"
    if text.startswith(("flutes_", "oboes_", "clarinets_", "bassoons_")):
        return "woodwinds"
    if text.startswith(("horns_", "trumpets_", "trombones_", "low_brass_")):
        return "brass"
    if text.startswith("timpani_"):
        return "timpani"
    if text.startswith("orchestral_percussion_"):
        return "orchestral_percussion"
    if text.startswith("cymbals_fx_"):
        return "fx"
    if text.startswith("choir_"):
        return "choir"
    if text.startswith("hybrid_pad_"):
        return "pad"
    if text in {"arp", "lead_answer", "lead_harmony", "counter", "counter_melody"}:
        return "melody"
    return text


def _orchestral_tracks(*, include_fx: bool = True) -> list[MusicTrack]:
    specs = [
        ("violins_i", 16, "Violins I Divisi", 0.22, 0.20, 0.54),
        ("violins_ii", 16, "Violins II Divisi", 0.20, 0.02, 0.38),
        ("violas", 12, "Violas Divisi", 0.20, -0.20, 0.12),
        ("cellos", 12, "Cellos Divisi", 0.23, -0.42, -0.10),
        ("contrabasses", 8, "Contrabasses", 0.24, -0.50, -0.22),
        ("flutes", 4, "Flutes", 0.15, 0.22, 0.42),
        ("oboes", 4, "Oboes", 0.15, 0.06, 0.26),
        ("clarinets", 4, "Clarinets", 0.16, -0.18, 0.08),
        ("bassoons", 4, "Bassoons", 0.17, -0.32, -0.12),
        ("horns", 8, "French Horns", 0.22, -0.18, 0.20),
        ("trumpets", 4, "Trumpets", 0.18, 0.18, 0.38),
        ("trombones", 4, "Trombones", 0.20, -0.34, -0.10),
        ("low_brass", 4, "Low Brass", 0.22, -0.22, 0.04),
        ("timpani", 4, "Timpani", 0.24, -0.08, 0.08),
        ("orchestral_percussion", 8, "Orchestral Percussion", 0.20, -0.20, 0.20),
        ("cymbals_fx" if include_fx else "hybrid_pad", 4, "Cymbals and Rises" if include_fx else "Hybrid Pads", 0.14, -0.06, 0.06),
        ("choir", 8, "Soft Choir", 0.13, -0.24, 0.24),
        ("hybrid_pad", 4, "Hybrid Cinematic Pad", 0.12, -0.10, 0.10),
    ]
    rows: list[MusicTrack] = []
    for prefix, count, instrument, volume, pan_left, pan_right in specs:
        for index in range(1, count + 1):
            ratio = 0.0 if count <= 1 else (index - 1) / float(count - 1)
            pan = pan_left + (pan_right - pan_left) * ratio
            voice_gain = 0.92 + ((index - 1) % 5) * 0.018
            role = f"{prefix}_{index:03d}"
            rows.append(_track(role, instrument, min(0.95, volume * voice_gain), pan))
    if len(rows) != ORCHESTRAL_TRACK_COUNT:
        raise AssertionError(f"orchestral track plan must create {ORCHESTRAL_TRACK_COUNT} tracks")
    return rows


def _default_music_tracks(*, include_fx: bool = True, melodic_edm: bool = False) -> list[MusicTrack]:
    if melodic_edm:
        tracks = [
            _track("drums", "Soft EDM Drum Kit", 0.70, 0.0),
            _track("bass", "Rounded Synth Bass", 0.66, -0.04),
            _track("bass_pulse", "Bass Pulse Layer", 0.36, 0.04),
            _track("chords", "Wide Smooth Pad", 0.54, 0.08),
            _track("arp", "Light Arp", 0.28, -0.18),
            _track("melody", "Clean Melodic Lead", 0.58, 0.14),
            _track("lead_answer", "Answer Lead", 0.36, -0.14),
            _track("counter", "Counter Melody", 0.24, 0.22),
        ]
        if include_fx:
            tracks.append(_track("fx", "Soft Impact FX", 0.25, 0.0))
        return tracks
    tracks = [
        _track("drums", "Creator Drum Kit", 0.68, 0.0),
        _track("bass", "Creator Bass", 0.62, -0.05),
        _track("bass_pulse", "Bass Pulse Layer", 0.30, 0.04),
        _track("chords", "Soft Pad", 0.52, 0.08),
        _track("arp", "Light Arp", 0.22, -0.18),
        _track("melody", "Muted Lead", 0.46, 0.14),
        _track("lead_answer", "Answer Lead", 0.28, -0.14),
        _track("counter", "Counter Melody", 0.20, 0.22),
    ]
    if include_fx:
        tracks.append(_track("fx", "Soft Impact FX", 0.22, 0.0))
    return tracks


def _generate_track_notes(track: MusicTrack, sections: list[MusicSection], *, bpm: int, key: str) -> None:
    track.clips = []
    beat_tick = TICKS_PER_BEAT
    bar_ms = int(round(60000.0 / max(1, bpm) * 4.0))
    role = str(track.role or "").lower()
    family = _role_family(role)
    lane = _role_index(role)
    for section in sections:
        clip = MidiClip(
            id=_clip_id(track.role, section.name),
            section_name=section.name,
            start_ms=section.start_ms,
            duration_ms=section.duration_ms,
        )
        bars = max(1, int(math.ceil(section.duration_ms / max(1, bar_ms))))
        section_tick = _ms_to_tick(section.start_ms, bpm)
        section_end_tick = section_tick + _ms_to_tick(section.duration_ms, bpm)
        if family == "drums":
            for bar in range(bars):
                bar_tick = section_tick + bar * beat_tick * 4
                for beat in range(4):
                    tick = bar_tick + beat * beat_tick
                    kick_velocity = int(76 + section.intensity * 23 + (3 if beat == 0 else 0))
                    clip.notes.append(MidiNote(36, tick, int(beat_tick * 0.45), kick_velocity))
                    if section.intensity > 0.78 and beat == 3 and bar % 2 == 1:
                        clip.notes.append(MidiNote(36, tick + int(beat_tick * 0.72), int(beat_tick * 0.18), int(62 + section.intensity * 12)))
                    if beat in {1, 3}:
                        clip.notes.append(MidiNote(38, tick, int(beat_tick * 0.35), int(70 + section.intensity * 22)))
                    if section.intensity > 0.72 and beat == 2:
                        clip.notes.append(MidiNote(38, tick + int(beat_tick * 0.48), int(beat_tick * 0.16), int(42 + section.intensity * 13)))
                    hat_steps = 2 if section.intensity < 0.7 else 4
                    for hat in range(hat_steps):
                        hat_tick = tick + int(hat * beat_tick / max(1, hat_steps))
                        hat_velocity = 40 + int(section.intensity * 22) + (5 if hat == 0 else -2)
                        clip.notes.append(MidiNote(42, hat_tick, int(beat_tick * 0.16), hat_velocity))
        elif family == "orchestral_percussion":
            accents = (0.0, 2.0) if section.intensity < 0.72 else (0.0, 1.5, 2.0, 3.5)
            pitch_cycle = (36, 38, 45, 49, 42)
            for bar in range(bars):
                bar_tick = section_tick + bar * beat_tick * 4
                for hit, beat_pos in enumerate(accents):
                    if (bar + lane + hit) % 5 == 0 and section.intensity < 0.85:
                        continue
                    pitch = pitch_cycle[(lane + hit + bar) % len(pitch_cycle)]
                    velocity = int(45 + section.intensity * 42 + (10 if beat_pos == 0.0 else 0))
                    clip.notes.append(MidiNote(pitch, bar_tick + int(beat_pos * beat_tick), int(beat_tick * 0.32), velocity))
        elif family == "timpani":
            for bar in range(bars):
                chord = section.chord_progression[bar % len(section.chord_progression)]
                root = _chord_root(chord, key) - 24 + (7 if lane % 4 in {2, 3} else 0)
                bar_tick = section_tick + bar * beat_tick * 4
                pattern = (0.0, 2.0, 3.5) if section.intensity > 0.68 else (0.0, 2.0)
                for beat_pos in pattern:
                    velocity = int(50 + section.intensity * 37 + (6 if beat_pos == 0.0 else 0))
                    clip.notes.append(MidiNote(root, bar_tick + int(beat_pos * beat_tick), int(beat_tick * 0.78), velocity))
        elif family == "bass":
            for bar in range(bars):
                chord = section.chord_progression[bar % len(section.chord_progression)]
                root = _chord_root(chord, key) - 12
                bar_tick = section_tick + bar * beat_tick * 4
                if role.startswith(("bass_pulse", "bass_layer")):
                    if section.intensity < 0.62:
                        continue
                    pattern = (1.75, 3.25) if bar % 2 else (0.75, 2.75, 3.5)
                else:
                    pattern = (0.0, 1.5, 2.0, 3.45) if section.intensity >= 0.72 else (0.0, 2.0, 3.0)
                for index, beat_pos in enumerate(pattern):
                    pitch = root + (7 if beat_pos >= 3.0 else 0) + (12 if role.startswith("bass_pulse") else 0)
                    if not role.startswith(("bass_pulse", "bass_layer")) and index == len(pattern) - 1 and section.intensity > 0.86:
                        pitch += 12
                    duration = int(beat_tick * (0.36 if role.startswith(("bass_pulse", "bass_layer")) else (0.86 if beat_pos in {0.0, 2.0} else 0.44)))
                    velocity = int((48 if role.startswith(("bass_pulse", "bass_layer")) else 68) + section.intensity * 21)
                    clip.notes.append(MidiNote(pitch, bar_tick + int(beat_pos * beat_tick), duration, velocity))
        elif family == "strings_low":
            for bar in range(bars):
                chord = section.chord_progression[bar % len(section.chord_progression)]
                root = _chord_root(chord, key) - (24 if role.startswith("contrabasses_") else 12)
                bar_tick = section_tick + bar * beat_tick * 4
                if role.startswith("contrabasses_"):
                    clip.notes.append(MidiNote(root, bar_tick, int(beat_tick * 3.72), int(43 + section.intensity * 26)))
                    if section.intensity > 0.76:
                        clip.notes.append(MidiNote(root + 7, bar_tick + int(beat_tick * 2.0), int(beat_tick * 1.6), int(38 + section.intensity * 18)))
                else:
                    pattern = (0.0, 1.0, 2.0, 3.0) if lane % 3 else (0.0, 1.5, 2.0, 3.5)
                    for step, beat_pos in enumerate(pattern):
                        pitch = root + (7 if (step + lane + bar) % 2 else 0) + (12 if step == 3 and section.intensity > 0.84 else 0)
                        clip.notes.append(MidiNote(pitch, bar_tick + int(beat_pos * beat_tick), int(beat_tick * 0.66), int(44 + section.intensity * 24)))
        elif family in {"chords", "pad", "choir"}:
            for bar in range(bars):
                chord = section.chord_progression[bar % len(section.chord_progression)]
                notes = _chord_voicing(chord, key, role="pad")
                bar_tick = section_tick + bar * beat_tick * 4
                strum = int(beat_tick * (0.026 + (lane % 5) * 0.004))
                for note_index, pitch in enumerate(notes):
                    octave = 12 if family == "choir" and lane % 4 in {0, 1} else 0
                    clip.notes.append(MidiNote(pitch + octave, bar_tick + note_index * strum, int(beat_tick * 3.82), int(35 + section.intensity * 19)))
        elif family in {"strings_mid", "strings_high"}:
            for bar in range(bars):
                chord = section.chord_progression[bar % len(section.chord_progression)]
                notes = _chord_voicing(chord, key, role="pad")
                bar_tick = section_tick + bar * beat_tick * 4
                base_pitch = notes[(lane + bar) % len(notes)]
                if family == "strings_high":
                    base_pitch += 12 if lane % 3 == 0 else 0
                else:
                    base_pitch -= 12 if lane % 5 == 0 else 0
                onset = int((lane % 4) * beat_tick * 0.035)
                clip.notes.append(MidiNote(base_pitch, bar_tick + onset, int(beat_tick * 3.58), int(38 + section.intensity * 25)))
                if section.intensity > 0.66 and (lane + bar) % 3 != 0:
                    passing = base_pitch + (2 if (lane + bar) % 2 else -2)
                    clip.notes.append(MidiNote(passing, bar_tick + int(beat_tick * 2.0) + onset, int(beat_tick * 0.82), int(32 + section.intensity * 18)))
        elif family == "brass":
            for bar in range(bars):
                chord = section.chord_progression[bar % len(section.chord_progression)]
                notes = _chord_voicing(chord, key, role="pad")
                bar_tick = section_tick + bar * beat_tick * 4
                pitch = notes[(lane + bar) % len(notes)] + (-12 if role.startswith(("trombones_", "low_brass_")) else 0)
                if section.intensity < 0.52 and bar % 2:
                    continue
                clip.notes.append(MidiNote(pitch, bar_tick, int(beat_tick * (2.9 if section.intensity > 0.7 else 1.8)), int(39 + section.intensity * 32)))
                if section.intensity > 0.82 and lane % 3 == 0:
                    clip.notes.append(MidiNote(pitch + 7, bar_tick + int(beat_tick * 3.0), int(beat_tick * 0.72), int(42 + section.intensity * 25)))
        elif family == "woodwinds":
            scale = [0, 2, 3 if _is_minor(key) else 4, 5, 7, 10 if _is_minor(key) else 9, 12]
            root = _root_pitch_for_key(key) + (24 if role.startswith(("bassoons_", "clarinets_")) else 36)
            for bar in range(bars):
                if section.intensity < 0.48 and (bar + lane) % 2:
                    continue
                bar_tick = section_tick + bar * beat_tick * 4
                for step in range(4):
                    degree = (lane + bar + step * 2) % len(scale)
                    tick = bar_tick + int((step + 0.5 * (lane % 2)) * beat_tick)
                    if tick >= section_end_tick:
                        break
                    pitch = root + scale[degree]
                    clip.notes.append(MidiNote(pitch, tick, int(beat_tick * 0.54), int(34 + section.intensity * 22)))
        elif family == "melody":
            scale = [0, 2, 3 if _is_minor(key) else 4, 5, 7, 10 if _is_minor(key) else 9, 12]
            root = _root_pitch_for_key(key) + 24
            motifs = (
                [0, 2, 4, 2, 5, 4, 2, 1],
                [2, 4, 5, 4, 2, 1, 0, 2],
                [4, 5, 6, 5, 4, 2, 1, 0],
            )
            for bar in range(bars):
                bar_tick = section_tick + bar * beat_tick * 4
                if role == "arp":
                    if section.intensity < 0.54:
                        continue
                    chord = section.chord_progression[bar % len(section.chord_progression)]
                    chord_notes = _chord_notes(chord, key, octave=2)
                    for step in range(8):
                        pitch = chord_notes[(step + bar) % len(chord_notes)] + (12 if step in {3, 7} and section.intensity > 0.78 else 0)
                        clip.notes.append(MidiNote(pitch, bar_tick + int(step * beat_tick / 2), int(beat_tick * 0.22), int(30 + section.intensity * 18)))
                    continue
                if role in {"lead_answer", "lead_harmony"}:
                    if section.intensity < 0.68 or bar % 2 == 0:
                        continue
                    answer = [0, 2, 4, 5, 4, 2]
                    for index, degree in enumerate(answer):
                        tick = bar_tick + int((index * 0.5 + 0.25) * beat_tick)
                        pitch = root + 12 + scale[degree % len(scale)] + (7 if role == "lead_harmony" and index in {2, 4} else 0)
                        clip.notes.append(MidiNote(pitch, tick, int(beat_tick * 0.34), int(36 + section.intensity * 20)))
                    continue
                if role.startswith("counter"):
                    if section.intensity < 0.78 or bar % 2:
                        continue
                    for index, degree in enumerate((4, 2, 0, 2)):
                        tick = bar_tick + int((index + 0.5) * beat_tick)
                        pitch = root + 12 + scale[degree % len(scale)] + 7
                        clip.notes.append(MidiNote(pitch, tick, int(beat_tick * 0.42), int(28 + section.intensity * 18)))
                    continue
                if section.intensity < 0.5 and bar % 2:
                    continue
                motif = motifs[(bar + len(section.name)) % len(motifs)]
                for index, degree in enumerate(motif):
                    if index in {3, 7} and (bar + index) % 3 == 0:
                        continue
                    tick = bar_tick + int(index * beat_tick / 2)
                    if tick >= section_tick + _ms_to_tick(section.duration_ms, bpm):
                        break
                    pitch = root + scale[degree % len(scale)]
                    duration = int(beat_tick * (0.58 if index in {0, 4} else 0.34))
                    velocity = int(49 + section.intensity * 24 + (5 if index in {0, 4} else 0))
                    clip.notes.append(MidiNote(pitch, tick, duration, velocity))
        elif family == "fx":
            clip.notes.append(MidiNote(72, section_tick, int(beat_tick * 1.5), int(50 + section.intensity * 34)))
            if role.startswith("cymbals_fx_") and section.intensity > 0.58:
                clip.notes.append(MidiNote(85, max(section_tick, section_end_tick - beat_tick), int(beat_tick * 1.1), int(42 + section.intensity * 30)))
        _trim_clip_notes_to_section(clip, section_start_tick=section_tick, section_end_tick=section_end_tick)
        track.clips.append(clip)


def compose_music(
    *,
    prompt: str = "",
    duration_ms: int = 30000,
    genre: str = "",
    mood: str = "",
    bpm: int | None = None,
    key: str = "",
    include_fx: bool = True,
) -> MusicComposition:
    prompt_text = _clean_text(prompt, "AI background music")
    genre_text = _clean_text(genre, "cinematic electronic")
    mood_text = _clean_text(mood, "confident")
    final_bpm = choose_bpm(prompt_text, genre_text, mood_text, bpm)
    final_key = choose_key(prompt_text, mood_text, key)
    duration = max(4000, min(180000, int(duration_ms or 30000)))
    melodic_edm = _is_melodic_edm_request(prompt_text, genre_text, mood_text)
    chords = chord_progression_for(final_key, genre_text, mood_text)
    sections = _edm_sections(duration, final_key, final_bpm) if melodic_edm else _sections(duration, chords)
    if melodic_edm and sections:
        duration = max(section.start_ms + section.duration_ms for section in sections)
    cid = composition_id(prompt_text, duration, genre_text, mood_text, final_bpm, final_key)
    if _is_orchestral_request(prompt_text, genre_text, mood_text):
        tracks = _orchestral_tracks(include_fx=include_fx)
    else:
        tracks = _default_music_tracks(
            include_fx=include_fx,
            melodic_edm=melodic_edm,
        )
    for track in tracks:
        _generate_track_notes(track, sections, bpm=final_bpm, key=final_key)
    return MusicComposition(
        id=cid,
        prompt=prompt_text,
        genre=genre_text,
        mood=mood_text,
        bpm=final_bpm,
        key=final_key,
        duration_ms=duration,
        sections=sections,
        tracks=tracks,
    )


def regenerate_section(composition: MusicComposition, section_name: str, *, mood: str = "", intensity: float | None = None) -> MusicComposition:
    target = str(section_name or "").strip().lower()
    if not target:
        raise ValueError("section_name is required")
    for section in composition.sections:
        if section.name.lower() != target:
            continue
        if intensity is not None:
            section.intensity = max(0.05, min(1.0, float(intensity)))
        if mood:
            composition.mood = _clean_text(mood, composition.mood)
        for track in composition.tracks:
            track.clips = [clip for clip in track.clips if clip.section_name.lower() != target]
            temp_track = MusicTrack(id=track.id, role=track.role, instrument=track.instrument, volume=track.volume, pan=track.pan)
            _generate_track_notes(temp_track, [section], bpm=composition.bpm, key=composition.key)
            track.clips.extend(temp_track.clips)
            track.clips.sort(key=lambda clip: clip.start_ms)
        composition.rendered_stems = {}
        composition.preview_mix_path = ""
        return composition
    raise ValueError(f"section not found: {section_name}")


def default_music_render_dir() -> Path:
    return Path.home() / "Videos" / "TigerCapture" / "Music Lab Renders"


def music_assets_root() -> Path:
    return Path(__file__).resolve().parents[1] / "external" / "assets" / "music"


def music_soundfont_dirs() -> list[Path]:
    paths: list[Path] = []
    env_value = os.environ.get("TIGERCAPTURE_MUSIC_SOUNDFONT_DIR", "")
    for raw in env_value.split(os.pathsep):
        if raw.strip():
            paths.append(Path(raw).expanduser())
    root = music_assets_root()
    paths.extend([root / "soundfonts", root / "sfz"])
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def discover_soundfonts(limit: int = 32) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for root in music_soundfont_dirs():
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() not in {".sf2", ".sf3", ".sfz"}:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            rows.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "format": path.suffix.lower().lstrip("."),
                    "size_bytes": int(size),
                }
            )
            if len(rows) >= max(1, int(limit)):
                return rows
    return rows


def find_fluidsynth_executable() -> str:
    env_value = os.environ.get("TIGERCAPTURE_FLUIDSYNTH_EXE", "").strip()
    candidates = []
    if env_value:
        candidates.append(Path(env_value).expanduser())
    which = shutil.which("fluidsynth")
    if which:
        candidates.append(Path(which))
    tool_root = Path(__file__).resolve().parents[1] / "external" / "tools" / "fluidsynth"
    candidates.extend(
        [
            tool_root / "bin" / "fluidsynth.exe",
            tool_root / "fluidsynth.exe",
            tool_root / "bin" / "fluidsynth",
            tool_root / "fluidsynth",
        ]
    )
    for path in candidates:
        try:
            if path.exists() and path.is_file():
                return str(path)
        except OSError:
            continue
    return ""


def music_production_renderer_status() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "external" / "tools" / "music_renderer" / "renderer.json"
    provider_config_path = repo_root / "external" / "tools" / "music_renderer" / "provider.json"
    env_exe = os.environ.get("TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_EXE", "").strip()
    env_args = os.environ.get("TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_ARGS", "").strip()
    command: list[str] = []
    source = ""
    supports_stems = False
    provider_config: dict[str, Any] = {}
    if provider_config_path.exists():
        try:
            loaded_provider_config = json.loads(provider_config_path.read_text(encoding="utf-8"))
        except Exception:
            loaded_provider_config = {}
        if isinstance(loaded_provider_config, dict):
            provider_config = loaded_provider_config

    def _resolve_config_arg(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return text
        path = Path(text).expanduser()
        if path.is_absolute():
            return str(path)
        for root in (repo_root, config_path.parent):
            candidate = root / path
            if candidate.exists():
                return str(candidate.resolve())
        return text

    if config_path.exists():
        try:
            row = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            row = {}
        exe = str(row.get("executable") or "").strip()
        if exe:
            command = [_resolve_config_arg(exe)] + [_resolve_config_arg(str(arg)) for arg in list(row.get("args") or [])]
            source = str(config_path)
            supports_stems = bool(row.get("supports_stems"))
    elif env_exe:
        command = [env_exe]
        if env_args:
            command.extend(shlex.split(env_args, posix=os.name != "nt"))
        source = "environment"
    executable_ready = False
    if command:
        executable = Path(command[0]).expanduser()
        executable_ready = executable.exists() or bool(shutil.which(command[0]))
    return {
        "backend": "production_external",
        "ready": executable_ready,
        "configured": bool(command),
        "source": source,
        "command": command,
        "supports_stems": supports_stems,
        "ai_provider_config": {
            "source": str(provider_config_path) if provider_config else "",
            "preferred_provider": str(provider_config.get("preferred_provider") or ""),
            "strict": bool(provider_config.get("strict")),
            "providers": {
                key: {
                    "enabled": bool(value.get("enabled")) if isinstance(value, dict) else False,
                    "base_url": str(value.get("base_url") or "") if isinstance(value, dict) else "",
                    "mode": str(value.get("mode") or "") if isinstance(value, dict) else "",
                    "space": str(value.get("space") or "") if isinstance(value, dict) else "",
                    "variant_key": str(value.get("variant_key") or "") if isinstance(value, dict) else "",
                }
                for key, value in dict(provider_config.get("providers") or {}).items()
            },
        },
        "quality_tier": MUSIC_QUALITY_PRODUCTION,
        "contract": "The renderer must accept --composition-json and --output-wav and write a stereo WAV mix.",
        "warning": "" if executable_ready else "No production music renderer is configured. Built-in renderers are draft/starter previews only.",
    }


def music_render_backend_status() -> dict[str, Any]:
    soundfonts = discover_soundfonts()
    fluidsynth = find_fluidsynth_executable()
    production = music_production_renderer_status()
    ready = bool(soundfonts and fluidsynth)
    warnings: list[str] = []
    if not soundfonts:
        warnings.append("No .sf2/.sf3/.sfz files found in external/assets/music/soundfonts.")
    if not fluidsynth:
        warnings.append("FluidSynth executable was not found in PATH or external/tools/fluidsynth.")
    if not production["ready"]:
        warnings.append(str(production["warning"]))
    return {
        "preferred_backend": "production_external" if production["ready"] else "fluidsynth_soundfont" if ready else "local_synth",
        "production_ready": bool(production["ready"]),
        "production_renderer": production,
        "soundfont_ready": bool(soundfonts),
        "fluidsynth_ready": bool(fluidsynth),
        "fluidsynth_path": fluidsynth,
        "soundfonts": soundfonts,
        "asset_dirs": [str(path) for path in music_soundfont_dirs()],
        "auto_policy": "production_external_when_configured_else_soundfont_first",
        "draft_synth_backend": "tigerstudio.studio_edm.v1",
        "fallback_backend": "tigerstudio.local_synth.v5",
        "quality_tiers": {
            "local_synth": MUSIC_QUALITY_DRAFT,
            "studio_edm": MUSIC_QUALITY_DRAFT,
            "fluidsynth_soundfont": MUSIC_QUALITY_STARTER,
            "production_external": MUSIC_QUALITY_PRODUCTION,
        },
        "quality_warning": "Music Lab's built-in renderers are composition drafts. Modern release-quality music requires a configured production renderer or licensed sample/model backend.",
        "warnings": warnings,
    }


def _select_soundfont(soundfont_path: str | Path | None = None) -> Path | None:
    if soundfont_path:
        path = Path(soundfont_path).expanduser()
        if path.exists() and path.suffix.lower() in {".sf2", ".sf3", ".sfz"}:
            return path
        raise FileNotFoundError(str(path))
    rows = discover_soundfonts(limit=1)
    if not rows:
        return None
    return Path(str(rows[0]["path"]))


def _pitch_to_hz(pitch: int) -> float:
    return 440.0 * (2.0 ** ((int(pitch) - 69) / 12.0))


def _soften_wave(data, passes: int = 1):
    import numpy as np

    out = data.astype(np.float32, copy=True)
    for _ in range(max(0, int(passes))):
        if out.size < 3:
            break
        smoothed = out.copy()
        smoothed[1:-1] = out[1:-1] * 0.5 + (out[:-2] + out[2:]) * 0.25
        out = smoothed
    return out


def _note_envelope(
    length: int,
    active_length: int,
    *,
    attack_s: float,
    decay_s: float,
    sustain: float,
    release_s: float,
):
    import numpy as np

    total = max(1, int(length))
    active = max(1, min(total, int(active_length)))
    env = np.full(total, max(0.0, min(1.0, float(sustain))), dtype=np.float32)
    attack = min(active, max(1, int(round(SAMPLE_RATE * max(0.0, attack_s)))))
    decay = min(max(0, active - attack), int(round(SAMPLE_RATE * max(0.0, decay_s))))
    if attack > 1:
        env[:attack] = np.linspace(0.0, 1.0, attack, dtype=np.float32)
    if decay > 1:
        env[attack:attack + decay] = np.linspace(1.0, env[attack + decay - 1], decay, dtype=np.float32)
    if active < total:
        start = float(env[active - 1])
        env[active:] = np.linspace(start, 0.0, total - active, dtype=np.float32)
    else:
        release = min(total, max(1, int(round(SAMPLE_RATE * max(0.0, release_s)))))
        if release > 1:
            env[-release:] *= np.linspace(1.0, 0.0, release, dtype=np.float32)
    return env


def _role_tail_seconds(role: str, note: MidiNote) -> float:
    family = _role_family(role)
    if family in {"chords", "pad", "choir"}:
        return 0.42
    if family in {"strings_mid", "strings_high", "brass"}:
        return 0.32
    if family == "strings_low":
        return 0.18
    if family == "woodwinds":
        return 0.16
    if family == "timpani":
        return 0.34
    if family == "melody":
        return 0.20
    if family == "bass":
        return 0.10
    if family == "fx":
        return 0.75
    if family in {"drums", "orchestral_percussion"} and note.pitch in {38, 42, 46}:
        return 0.04
    return 0.02


def _note_seed(note: MidiNote, role: str) -> int:
    return int(note.start_tick * 31 + note.pitch * 997 + len(str(role)) * 131)


def _humanize_note(role: str, note: MidiNote) -> tuple[float, float]:
    import numpy as np

    rng = np.random.default_rng(_note_seed(note, role))
    family = _role_family(role)
    if family in {"drums", "orchestral_percussion"}:
        if note.pitch == 36:
            return 0.0, float(rng.uniform(0.98, 1.03))
        if note.pitch == 38:
            return float(rng.uniform(-1.5, 2.5)), float(rng.uniform(0.94, 1.06))
        return float(rng.uniform(-3.0, 4.5)), float(rng.uniform(0.82, 1.05))
    if family in {"chords", "pad", "choir", "strings_mid", "strings_high", "brass"}:
        return float(rng.uniform(-2.0, 8.0)), float(rng.uniform(0.92, 1.04))
    if family in {"bass", "strings_low", "timpani"}:
        return float(rng.uniform(-2.5, 4.0)), float(rng.uniform(0.95, 1.05))
    if family in {"melody", "woodwinds"}:
        return float(rng.uniform(-4.0, 7.0)), float(rng.uniform(0.88, 1.08))
    return float(rng.uniform(-2.0, 5.0)), float(rng.uniform(0.92, 1.04))


def _render_note_tone(samples, note: MidiNote, *, bpm: int, role: str, volume: float, pan: float) -> None:
    import numpy as np

    family = _role_family(role)
    start_s = note.start_tick / TICKS_PER_BEAT * 60.0 / max(1, bpm)
    dur_s = max(0.03, note.duration_tick / TICKS_PER_BEAT * 60.0 / max(1, bpm))
    jitter_ms, velocity_scale = _humanize_note(role, note)
    start = max(0, int(round(start_s * SAMPLE_RATE + jitter_ms * SAMPLE_RATE / 1000.0)))
    active_length = max(1, int(round(dur_s * SAMPLE_RATE)))
    tail_length = int(round(_role_tail_seconds(role, note) * SAMPLE_RATE))
    length = max(1, active_length + tail_length)
    end = min(samples.shape[0], start + length)
    if end <= start:
        return
    local_len = end - start
    active_len = max(1, min(active_length, local_len))
    t = np.arange(local_len, dtype=np.float32) / float(SAMPLE_RATE)
    amp = max(0.0, min(1.0, note.velocity / 127.0)) * max(0.0, min(1.2, volume)) * max(0.2, min(1.4, velocity_scale))
    if family in {"drums", "orchestral_percussion"}:
        if note.pitch == 36:
            freq = 48.0 * np.exp(-t * 9.0) + 38.0
            click = np.sin(2.0 * np.pi * 1700.0 * t) * np.exp(-t * 84.0) * 0.08
            body = np.sin(2.0 * np.pi * freq * t) * np.exp(-t * 9.0)
            wave_data = (body + click) * amp * 0.88
        elif note.pitch == 38:
            rng = np.random.default_rng(int(note.start_tick + note.pitch))
            noise = rng.normal(0.0, 1.0, local_len).astype(np.float32)
            noise = _soften_wave(noise, passes=2)
            tone = np.sin(2.0 * np.pi * 196.0 * t) * np.exp(-t * 15.0)
            snap = np.sin(2.0 * np.pi * 2600.0 * t) * np.exp(-t * 52.0)
            wave_data = (noise * np.exp(-t * 24.0) * 0.24 + tone * 0.17 + snap * 0.035) * amp
        else:
            rng = np.random.default_rng(int(note.start_tick + note.pitch))
            noise = rng.normal(0.0, 1.0, local_len).astype(np.float32)
            noise = _soften_wave(noise, passes=5)
            shimmer = np.sin(2.0 * np.pi * 4200.0 * t) * np.exp(-t * 24.0)
            env = _note_envelope(local_len, active_len, attack_s=0.006, decay_s=0.035, sustain=0.08, release_s=0.045)
            wave_data = (noise * 0.045 + shimmer * 0.010) * env * amp
    else:
        hz = _pitch_to_hz(note.pitch)
        sine = np.sin(2.0 * np.pi * hz * t)
        if family == "timpani":
            sub = np.sin(2.0 * np.pi * hz * 0.5 * t)
            second = np.sin(2.0 * np.pi * hz * 2.0 * t)
            env = _note_envelope(local_len, active_len, attack_s=0.012, decay_s=0.22, sustain=0.42, release_s=0.34)
            roll = 1.0 + 0.035 * np.sin(2.0 * np.pi * 11.0 * t)
            wave_data = _soften_wave(sine * 0.70 + sub * 0.42 + second * 0.08, passes=2) * env * amp * 0.34 * roll
        elif family in {"bass", "strings_low"}:
            sub = np.sin(2.0 * np.pi * hz * 0.5 * t)
            second = np.sin(2.0 * np.pi * hz * 2.0 * t)
            third = np.sin(2.0 * np.pi * hz * 3.0 * t)
            attack = 0.055 if family == "strings_low" else 0.007
            release = 0.18 if family == "strings_low" else 0.10
            env = _note_envelope(local_len, active_len, attack_s=attack, decay_s=0.12, sustain=0.66, release_s=release)
            bow = 0.96 + 0.04 * np.sin(2.0 * np.pi * 4.1 * t)
            body = np.tanh((sine * 0.64 + sub * 0.34 + second * 0.10 + third * 0.035) * 1.04)
            wave_data = _soften_wave(body, passes=2) * env * amp * (0.30 if family == "strings_low" else 0.38) * bow
        elif family in {"chords", "pad", "choir"}:
            detune_a = np.sin(2.0 * np.pi * hz * 0.996 * t + 0.33)
            detune_b = np.sin(2.0 * np.pi * hz * 1.004 * t + 1.12)
            octave = np.sin(2.0 * np.pi * hz * 0.5 * t + 0.74)
            fifth = np.sin(2.0 * np.pi * hz * 1.5 * t + 1.7)
            lfo = 0.94 + 0.06 * np.sin(2.0 * np.pi * 0.21 * t)
            env = _note_envelope(local_len, active_len, attack_s=0.22 if family == "choir" else 0.18, decay_s=0.34, sustain=0.82, release_s=0.46)
            wave = (sine * 0.38 + detune_a * 0.28 + detune_b * 0.25 + octave * 0.16 + fifth * 0.07)
            breath = 0.0
            if family == "choir":
                rng = np.random.default_rng(int(note.start_tick + note.pitch * 11))
                breath = _soften_wave(rng.normal(0.0, 1.0, local_len).astype(np.float32), passes=5) * 0.012
            wave_data = _soften_wave(wave, passes=3) * env * amp * (0.105 if family == "choir" else 0.13) * lfo + breath * env * amp
        elif family in {"strings_mid", "strings_high"}:
            detune_a = np.sin(2.0 * np.pi * hz * 0.998 * t + 0.21)
            detune_b = np.sin(2.0 * np.pi * hz * 1.003 * t + 1.4)
            harmonic = np.sin(2.0 * np.pi * hz * 2.0 * t + 0.17)
            vibrato = 0.0022 * np.sin(2.0 * np.pi * 5.2 * t) * np.minimum(1.0, t / 0.35)
            vib = np.sin(2.0 * np.pi * hz * (1.0 + vibrato) * t)
            env = _note_envelope(local_len, active_len, attack_s=0.075, decay_s=0.24, sustain=0.74, release_s=0.32)
            wave = vib * 0.44 + detune_a * 0.24 + detune_b * 0.22 + harmonic * 0.045
            wave_data = _soften_wave(wave, passes=3) * env * amp * (0.15 if family == "strings_high" else 0.17)
        elif family == "brass":
            second = np.sin(2.0 * np.pi * hz * 2.0 * t + 0.2)
            third = np.sin(2.0 * np.pi * hz * 3.0 * t + 0.5)
            swell = np.minimum(1.0, 0.55 + t / max(0.2, dur_s))
            env = _note_envelope(local_len, active_len, attack_s=0.055, decay_s=0.18, sustain=0.68, release_s=0.30)
            wave = np.tanh((sine * 0.62 + second * 0.22 + third * 0.075) * 1.1)
            wave_data = _soften_wave(wave, passes=2) * env * amp * 0.19 * swell
        elif family == "woodwinds":
            vib_depth = 0.0026 * np.minimum(1.0, t / 0.18)
            vibrato = vib_depth * np.sin(2.0 * np.pi * 5.7 * t)
            vib_sine = np.sin(2.0 * np.pi * hz * (1.0 + vibrato) * t)
            harmonic = np.sin(2.0 * np.pi * hz * 2.0 * t + 0.28)
            rng = np.random.default_rng(int(note.start_tick + note.pitch * 23))
            breath = _soften_wave(rng.normal(0.0, 1.0, local_len).astype(np.float32), passes=4) * np.exp(-t * 18.0)
            env = _note_envelope(local_len, active_len, attack_s=0.026, decay_s=0.18, sustain=0.42, release_s=0.16)
            wave_data = _soften_wave(vib_sine * 0.70 + harmonic * 0.10 + breath * 0.022, passes=2) * env * amp * 0.18
        elif family == "fx":
            rng = np.random.default_rng(int(note.start_tick + note.pitch * 17))
            noise = _soften_wave(rng.normal(0.0, 1.0, local_len).astype(np.float32), passes=4)
            sweep = np.sin(2.0 * np.pi * hz * (1.0 + t * 0.18) * t)
            env = _note_envelope(local_len, active_len, attack_s=0.04, decay_s=0.30, sustain=0.30, release_s=0.75)
            wave_data = (sweep * 0.48 + noise * 0.08) * env * amp * 0.17
        else:
            vib_depth = 0.0028 * np.minimum(1.0, t / 0.22)
            vibrato = vib_depth * np.sin(2.0 * np.pi * 5.0 * t)
            vib_sine = np.sin(2.0 * np.pi * hz * (1.0 + vibrato) * t)
            harmonic = np.sin(2.0 * np.pi * hz * 2.0 * t + 0.41)
            rng = np.random.default_rng(int(note.start_tick + note.pitch * 31))
            breath = _soften_wave(rng.normal(0.0, 1.0, local_len).astype(np.float32), passes=3) * np.exp(-t * 24.0)
            env = _note_envelope(local_len, active_len, attack_s=0.010, decay_s=0.18, sustain=0.26, release_s=0.20)
            wave = vib_sine * 0.74 + harmonic * 0.12 + breath * 0.018
            wave_data = _soften_wave(wave, passes=2) * env * amp * 0.21
    left_gain = math.sqrt(max(0.0, min(1.0, (1.0 - pan) * 0.5)))
    right_gain = math.sqrt(max(0.0, min(1.0, (1.0 + pan) * 0.5)))
    samples[start:end, 0] += wave_data[:local_len] * left_gain
    samples[start:end, 1] += wave_data[:local_len] * right_gain


def _box_filter(samples, window: int):
    import numpy as np

    width = max(1, int(window))
    if width <= 1 or samples.shape[0] < width:
        return samples.astype(np.float32, copy=True)
    if width % 2 == 0:
        width += 1
    pad = width // 2
    padded = np.pad(samples.astype(np.float32, copy=False), ((pad, pad), (0, 0)), mode="edge")
    csum = np.cumsum(np.vstack([np.zeros((1, padded.shape[1]), dtype=np.float32), padded]), axis=0, dtype=np.float64)
    return ((csum[width:] - csum[:-width]) / float(width)).astype(np.float32)


def _shape_stem(role: str, samples) -> None:
    import numpy as np

    if samples.size == 0:
        return
    role_text = _role_family(role)
    if role_text in {"drums", "orchestral_percussion"}:
        body = _box_filter(samples, 5)
        snap = samples - _box_filter(samples, 17)
        samples[:] = body * 0.92 + snap * 0.82
    elif role_text in {"bass", "strings_low", "timpani"}:
        low = _box_filter(samples, 41)
        mid = samples - _box_filter(samples, 13)
        samples[:] = low * 1.00 + mid * 0.28
    elif role_text in {"chords", "pad", "choir", "strings_mid", "strings_high", "brass"}:
        low = _box_filter(samples, 113)
        smooth = _box_filter(samples, 9)
        samples[:] = (smooth - low * 0.28) * 0.92
    elif role_text in {"melody", "woodwinds"}:
        smooth = _box_filter(samples, 5)
        bite = samples - _box_filter(samples, 21)
        samples[:] = smooth * 0.86 + bite * 0.18
    elif role_text == "fx":
        samples[:] = _box_filter(samples, 7) * 0.90
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak > 1.15:
        samples[:] = samples / peak * 1.15


def _polish_stereo(samples, *, master: bool = False) -> None:
    import numpy as np

    if samples.size == 0:
        return
    width_delay = int(SAMPLE_RATE * 0.012)
    if 1 <= width_delay < samples.shape[0]:
        left = samples[:-width_delay, 0].copy()
        right = samples[:-width_delay, 1].copy()
        samples[width_delay:, 0] += right * 0.022
        samples[width_delay:, 1] += left * 0.022
    room_delay = int(SAMPLE_RATE * 0.043)
    if 1 <= room_delay < samples.shape[0]:
        room = samples[:-room_delay].copy()
        samples[room_delay:, 0] += room[:, 1] * 0.018
        samples[room_delay:, 1] += room[:, 0] * 0.018
    tail_delay = int(SAMPLE_RATE * 0.087)
    if 1 <= tail_delay < samples.shape[0]:
        tail = samples[:-tail_delay].copy()
        samples[tail_delay:] += tail * 0.010
    if master:
        glue = _box_filter(samples, 3)
        low = _box_filter(samples, 151)
        samples[:] = glue * 0.96 + low * 0.018
        samples[:] = np.tanh(samples * 1.02) * 0.975
    else:
        samples[:] = np.tanh(samples * 1.035) * 0.965


def _normalize_preview_mix(samples) -> None:
    import numpy as np

    if samples.size == 0:
        return
    peak = float(np.max(np.abs(samples)))
    if peak <= 0.000001:
        return
    rms = float(np.sqrt(np.mean(samples * samples)))
    target_peak = 0.82
    target_rms = 0.055
    peak_gain = target_peak / peak
    rms_gain = target_rms / rms if rms > 0.000001 else peak_gain
    gain = max(1.0, min(24.0, peak_gain, rms_gain))
    samples[:] = samples * gain
    peak = float(np.max(np.abs(samples)))
    if peak > 0.92:
        samples[:] = samples / peak * 0.92


def _normalize_mix(samples, *, target_peak: float = 0.88, target_rms: float = 0.075) -> None:
    import numpy as np

    if samples.size == 0:
        return
    peak = float(np.max(np.abs(samples)))
    if peak <= 0.000001:
        return
    rms = float(np.sqrt(np.mean(samples * samples)))
    peak_gain = max(0.01, float(target_peak)) / peak
    rms_gain = max(0.001, float(target_rms)) / rms if rms > 0.000001 else peak_gain
    gain = max(1.0, min(28.0, peak_gain, rms_gain))
    samples[:] *= gain
    peak = float(np.max(np.abs(samples)))
    if peak > target_peak:
        samples[:] = samples / peak * target_peak


def _studio_polish_mix(samples) -> None:
    import numpy as np

    if samples.size == 0:
        return
    dry = samples.astype(np.float32, copy=True)
    low = _box_filter(dry, 301)
    mid = dry - _box_filter(dry, 31)
    samples[:] = dry * 0.92 + mid * 0.08 - low * 0.015
    room_delay = int(SAMPLE_RATE * 0.031)
    if 1 <= room_delay < samples.shape[0]:
        room = samples[:-room_delay].copy()
        samples[room_delay:, 0] += room[:, 1] * 0.026
        samples[room_delay:, 1] += room[:, 0] * 0.026
    slap_delay = int(SAMPLE_RATE * 0.079)
    if 1 <= slap_delay < samples.shape[0]:
        tail = samples[:-slap_delay].copy()
        samples[slap_delay:] += tail * 0.012
    if samples.shape[1] >= 2:
        mid_channel = (samples[:, 0] + samples[:, 1]) * 0.5
        side_channel = (samples[:, 0] - samples[:, 1]) * 0.5 * 1.08
        samples[:, 0] = mid_channel + side_channel
        samples[:, 1] = mid_channel - side_channel
    parallel = np.tanh(samples * 1.7) / 1.7
    samples[:] = samples * 0.72 + parallel * 0.28
    samples[:] = _box_filter(samples, 3) * 0.72 + samples * 0.28


def _write_wav(path: Path, samples) -> None:
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    samples = samples.astype(np.float32, copy=True)
    if samples.shape[0] > 1:
        fade_in = min(samples.shape[0], max(1, int(round(SAMPLE_RATE * 0.006))))
        fade_out = min(samples.shape[0], max(1, int(round(SAMPLE_RATE * 0.090))))
        samples[:fade_in] *= np.linspace(0.0, 1.0, fade_in, dtype=np.float32)[:, None]
        samples[-fade_out:] *= np.linspace(1.0, 0.0, fade_out, dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak > 0.98:
        samples = samples / peak * 0.98
    data = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(data.tobytes())


def _normalize_existing_mix_wav(path: Path) -> None:
    import numpy as np

    if not path.exists() or path.stat().st_size <= 44:
        return
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        frames = handle.getnframes()
        data = handle.readframes(frames)
    if width != 2 or channels not in {1, 2} or not data:
        return
    samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    if channels == 2:
        samples = samples.reshape(-1, 2)
    else:
        samples = np.repeat(samples.reshape(-1, 1), 2, axis=1)
    _studio_polish_mix(samples)
    _normalize_preview_mix(samples)
    _write_wav(path, samples)


def _composition_subset(composition: MusicComposition, tracks: list[MusicTrack], *, suffix: str) -> MusicComposition:
    return MusicComposition(
        id=f"{composition.id}_{suffix}",
        prompt=composition.prompt,
        genre=composition.genre,
        mood=composition.mood,
        bpm=composition.bpm,
        key=composition.key,
        duration_ms=composition.duration_ms,
        ticks_per_beat=composition.ticks_per_beat,
        sections=list(composition.sections),
        tracks=tracks,
    )


def _run_fluidsynth(
    *,
    fluidsynth_path: str,
    soundfont_path: Path,
    midi_path: Path,
    wav_path: Path,
    timeout_s: float,
) -> None:
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(fluidsynth_path),
        "-ni",
        "-R",
        "yes",
        "-C",
        "yes",
        "-g",
        "0.64",
        "-F",
        str(wav_path.resolve()),
        "-r",
        str(SAMPLE_RATE),
        str(soundfont_path.resolve()),
        str(midi_path.resolve()),
    ]
    completed = subprocess.run(
        command,
        cwd=str(wav_path.parent),
        capture_output=True,
        text=True,
        timeout=max(20.0, float(timeout_s)),
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"FluidSynth render failed ({completed.returncode}): {stderr[:500]}")
    if not wav_path.exists() or wav_path.stat().st_size <= 44:
        raise RuntimeError("FluidSynth did not produce a usable WAV file")


def _render_soundfont_preview(
    composition: MusicComposition,
    *,
    output_dir: Path,
    soundfont_path: Path,
    fluidsynth_path: str,
    render_stems: bool = True,
) -> dict[str, Any]:
    midi_cache = output_dir / f"{composition.id}_midi_cache"
    midi_cache.mkdir(parents=True, exist_ok=True)
    stems: dict[str, str] = {}
    timeout_s = max(30.0, composition.duration_ms / 1000.0 + 40.0)
    if render_stems:
        for track in composition.tracks:
            subset = _composition_subset(composition, [track], suffix=track.role)
            midi_path = midi_cache / f"{subset.id}.mid"
            wav_path = output_dir / f"{composition.id}_{track.role}.wav"
            export_midi(subset, output_path=midi_path)
            _run_fluidsynth(
                fluidsynth_path=fluidsynth_path,
                soundfont_path=soundfont_path,
                midi_path=midi_path,
                wav_path=wav_path,
                timeout_s=timeout_s,
            )
            stems[track.role] = str(wav_path)
    mix_midi = midi_cache / f"{composition.id}_mix.mid"
    mix_path = output_dir / f"{composition.id}_mix.wav"
    export_midi(composition, output_path=mix_midi)
    _run_fluidsynth(
        fluidsynth_path=fluidsynth_path,
        soundfont_path=soundfont_path,
        midi_path=mix_midi,
        wav_path=mix_path,
        timeout_s=timeout_s,
    )
    _normalize_existing_mix_wav(mix_path)
    composition.rendered_stems = stems
    composition.preview_mix_path = str(mix_path)
    composition.render_engine = "fluidsynth.soundfont.v1"
    composition.render_backend = {
        "backend": "fluidsynth_soundfont",
        "soundfont_path": str(soundfont_path),
        "fluidsynth_path": str(fluidsynth_path),
        "render_stems": bool(render_stems),
        "quality_tier": MUSIC_QUALITY_STARTER,
        "production_ready": False,
        "quality_warning": "Starter SoundFont preview only; not a modern production music renderer.",
    }
    return {
        "composition_id": composition.id,
        "output_dir": str(output_dir),
        "stems": dict(stems),
        "preview_mix_path": str(mix_path),
        "render_engine": composition.render_engine,
        "render_backend": dict(composition.render_backend),
    }


def _render_external_production_preview(
    composition: MusicComposition,
    *,
    output_dir: Path,
    requested_backend: str,
    render_stems: bool = True,
) -> dict[str, Any]:
    status = music_production_renderer_status()
    if not status.get("ready"):
        raise RuntimeError(
            "Production music rendering is not configured. "
            "Set external/tools/music_renderer/renderer.json or "
            "TIGERCAPTURE_MUSIC_PRODUCTION_RENDERER_EXE. Built-in renderers are draft/starter previews only."
        )
    if render_stems and not bool(status.get("supports_stems")):
        raise RuntimeError("The configured production music renderer does not advertise stem rendering support.")
    output_dir.mkdir(parents=True, exist_ok=True)
    request_path = output_dir / f"{composition.id}_production_request.json"
    mix_path = output_dir / f"{composition.id}_production_mix.wav"
    request_path.write_text(
        json.dumps(
            {
                "schema": MUSIC_SCHEMA,
                "composition": composition.to_dict(),
                "output_wav": str(mix_path.resolve()),
                "render_stems": bool(render_stems),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    command = [str(part) for part in list(status.get("command") or [])]
    command.extend(["--composition-json", str(request_path.resolve()), "--output-wav", str(mix_path.resolve())])
    completed = subprocess.run(
        command,
        cwd=str(output_dir.resolve()),
        capture_output=True,
        text=True,
        timeout=max(60.0, composition.duration_ms / 1000.0 * 4.0 + 60.0),
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Production music renderer failed ({completed.returncode}): {detail[:700]}")
    if not mix_path.exists() or mix_path.stat().st_size <= 44:
        raise RuntimeError("Production music renderer did not produce a usable WAV mix.")
    renderer_meta: dict[str, Any] = {}
    meta_path = mix_path.with_suffix(mix_path.suffix + ".renderer.json")
    if meta_path.exists():
        try:
            loaded_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            loaded_meta = {}
        if isinstance(loaded_meta, dict):
            renderer_meta = loaded_meta
    composition.rendered_stems = {}
    composition.preview_mix_path = str(mix_path)
    composition.render_engine = "production.external_music_renderer.v1"
    composition.render_backend = {
        "backend": "production_external",
        "requested_backend": requested_backend,
        "renderer_source": str(status.get("source") or ""),
        "provider": str(renderer_meta.get("provider") or ""),
        "provider_engine": str(renderer_meta.get("provider_engine") or ""),
        "fallback_used": bool(renderer_meta.get("fallback_used")),
        "fallback_reason": str(renderer_meta.get("fallback_reason") or ""),
        "render_stems": bool(render_stems),
        "quality_tier": MUSIC_QUALITY_PRODUCTION,
        "production_ready": True,
    }
    return {
        "composition_id": composition.id,
        "output_dir": str(output_dir),
        "stems": {},
        "preview_mix_path": str(mix_path),
        "render_engine": composition.render_engine,
        "render_backend": dict(composition.render_backend),
    }


def _composition_is_melodic_edm(composition: MusicComposition) -> bool:
    return _is_melodic_edm_request(composition.prompt, composition.genre, composition.mood)


def _edm_saw_stack(hz: float, t, *, detunes: tuple[float, ...] = (-0.006, -0.002, 0.0, 0.003, 0.007), harmonics: int = 7):
    import numpy as np

    out = np.zeros_like(t, dtype=np.float32)
    for detune in detunes:
        freq = max(12.0, float(hz) * (1.0 + float(detune)))
        phase = 2.0 * np.pi * freq * t
        voice = np.zeros_like(t, dtype=np.float32)
        for harmonic in range(1, max(2, int(harmonics)) + 1):
            voice += np.sin(phase * harmonic) / float(harmonic)
        out += voice
    return out / max(1.0, float(len(detunes))) * 0.62


def _edm_note_window(note: MidiNote, *, bpm: int, tail_s: float) -> tuple[int, int, int, int]:
    start_s = note.start_tick / TICKS_PER_BEAT * 60.0 / max(1, bpm)
    dur_s = max(0.025, note.duration_tick / TICKS_PER_BEAT * 60.0 / max(1, bpm))
    start = max(0, int(round(start_s * SAMPLE_RATE)))
    active = max(1, int(round(dur_s * SAMPLE_RATE)))
    total = max(1, active + int(round(max(0.0, tail_s) * SAMPLE_RATE)))
    return start, start + total, active, total


def _render_studio_edm_note(samples, note: MidiNote, *, bpm: int, role: str, volume: float, pan: float) -> None:
    import numpy as np

    family = _role_family(role)
    role_text = str(role or "").lower()
    tail = 0.55 if family in {"chords", "pad"} else 0.34 if family == "melody" else 0.12
    if family == "drums":
        tail = 0.18 if note.pitch == 36 else 0.24 if note.pitch == 38 else 0.06
    if family == "fx":
        tail = 1.2
    start, end, active_len, total_len = _edm_note_window(note, bpm=bpm, tail_s=tail)
    end = min(samples.shape[0], end)
    if end <= start:
        return
    local_len = end - start
    active = max(1, min(active_len, local_len))
    t = np.arange(local_len, dtype=np.float32) / float(SAMPLE_RATE)
    amp = max(0.0, min(1.0, note.velocity / 127.0)) * max(0.0, min(1.4, volume))

    if family == "drums":
        if note.pitch == 36:
            freq = 112.0 * np.exp(-t * 34.0) + 43.0
            body = np.sin(2.0 * np.pi * freq * t) * np.exp(-t * 7.4)
            sub = np.sin(2.0 * np.pi * 46.0 * t) * np.exp(-t * 5.5)
            click = np.sin(2.0 * np.pi * 3100.0 * t) * np.exp(-t * 88.0) * 0.045
            env = _note_envelope(local_len, active, attack_s=0.0015, decay_s=0.07, sustain=0.12, release_s=0.10)
            wave_data = np.tanh((body * 1.08 + sub * 0.52 + click) * 1.45) * env * amp * 0.95
        elif note.pitch == 38:
            rng = np.random.default_rng(int(note.start_tick + note.pitch * 13))
            noise = _soften_wave(rng.normal(0.0, 1.0, local_len).astype(np.float32), passes=3)
            tone = np.sin(2.0 * np.pi * 185.0 * t) * np.exp(-t * 9.0)
            snap = np.sin(2.0 * np.pi * 1700.0 * t) * np.exp(-t * 38.0)
            env = _note_envelope(local_len, active, attack_s=0.003, decay_s=0.09, sustain=0.20, release_s=0.16)
            wave_data = (noise * 0.18 + tone * 0.24 + snap * 0.035) * env * amp * 0.62
        else:
            rng = np.random.default_rng(int(note.start_tick + note.pitch * 19))
            noise = _soften_wave(rng.normal(0.0, 1.0, local_len).astype(np.float32), passes=6)
            env = _note_envelope(local_len, active, attack_s=0.004, decay_s=0.035, sustain=0.04, release_s=0.045)
            shimmer = np.sin(2.0 * np.pi * 5200.0 * t) * np.exp(-t * 20.0)
            wave_data = (noise * 0.032 + shimmer * 0.007) * env * amp
    elif family == "bass":
        hz = _pitch_to_hz(note.pitch)
        sub = np.sin(2.0 * np.pi * hz * 0.5 * t)
        body = np.sin(2.0 * np.pi * hz * t)
        edge = _edm_saw_stack(hz, t, detunes=(-0.002, 0.0, 0.002), harmonics=5)
        env = _note_envelope(local_len, active, attack_s=0.006, decay_s=0.08, sustain=0.72, release_s=0.10)
        edge_gain = 0.20 if role_text.startswith("bass_pulse") else 0.14
        wave_data = np.tanh((sub * 0.68 + body * 0.34 + edge * edge_gain) * 1.35) * env * amp * 0.46
    elif family in {"chords", "pad"}:
        hz = _pitch_to_hz(note.pitch)
        wave = _edm_saw_stack(hz, t, detunes=(-0.009, -0.004, 0.0, 0.004, 0.010), harmonics=6)
        octave = _edm_saw_stack(hz * 0.5, t, detunes=(-0.003, 0.002), harmonics=4)
        lfo = 0.90 + 0.10 * np.sin(2.0 * np.pi * 0.18 * t)
        env = _note_envelope(local_len, active, attack_s=0.16, decay_s=0.32, sustain=0.82, release_s=0.55)
        wave_data = _soften_wave(wave * 0.58 + octave * 0.18, passes=3) * env * amp * 0.145 * lfo
    elif family == "melody":
        hz = _pitch_to_hz(note.pitch)
        if role_text == "arp":
            wave = _edm_saw_stack(hz, t, detunes=(-0.003, 0.0, 0.003), harmonics=5)
            env = _note_envelope(local_len, active, attack_s=0.006, decay_s=0.08, sustain=0.18, release_s=0.18)
            wave_data = np.tanh(wave * 1.18) * env * amp * 0.18
        elif role_text in {"lead_answer", "lead_harmony", "counter", "counter_melody"}:
            wave = _edm_saw_stack(hz, t, detunes=(-0.006, 0.0, 0.006), harmonics=6)
            sine = np.sin(2.0 * np.pi * hz * t)
            env = _note_envelope(local_len, active, attack_s=0.014, decay_s=0.16, sustain=0.36, release_s=0.24)
            wave_data = _soften_wave(wave * 0.72 + sine * 0.20, passes=2) * env * amp * 0.16
        else:
            wave = _edm_saw_stack(hz, t, detunes=(-0.010, -0.004, 0.0, 0.005, 0.011), harmonics=7)
            sine = np.sin(2.0 * np.pi * hz * t)
            env = _note_envelope(local_len, active, attack_s=0.012, decay_s=0.12, sustain=0.46, release_s=0.26)
            wave_data = np.tanh((wave * 0.86 + sine * 0.16) * 1.12) * env * amp * 0.20
    elif family == "fx":
        hz = _pitch_to_hz(note.pitch)
        rng = np.random.default_rng(int(note.start_tick + note.pitch * 31))
        noise = _soften_wave(rng.normal(0.0, 1.0, local_len).astype(np.float32), passes=6)
        sweep = np.sin(2.0 * np.pi * hz * (1.0 + t * 0.45) * t)
        env = _note_envelope(local_len, active, attack_s=0.08, decay_s=0.42, sustain=0.18, release_s=0.9)
        wave_data = (noise * 0.055 + sweep * 0.22) * env * amp * 0.24
    else:
        hz = _pitch_to_hz(note.pitch)
        env = _note_envelope(local_len, active, attack_s=0.010, decay_s=0.18, sustain=0.30, release_s=0.20)
        wave_data = np.sin(2.0 * np.pi * hz * t) * env * amp * 0.16

    left_gain = math.sqrt(max(0.0, min(1.0, (1.0 - pan) * 0.5)))
    right_gain = math.sqrt(max(0.0, min(1.0, (1.0 + pan) * 0.5)))
    samples[start:end, 0] += wave_data[:local_len] * left_gain
    samples[start:end, 1] += wave_data[:local_len] * right_gain


def _apply_edm_sidechain(samples, *, bpm: int, amount: float = 0.32) -> None:
    import numpy as np

    if samples.size == 0:
        return
    beat_s = 60.0 / max(1, bpm)
    t = np.arange(samples.shape[0], dtype=np.float32) / float(SAMPLE_RATE)
    phase = (t % beat_s) / beat_s
    duck = 1.0 - max(0.0, min(0.85, float(amount))) * np.exp(-phase * 7.5)
    samples[:] *= duck[:, None]


def _studio_edm_bus(samples) -> None:
    import numpy as np

    if samples.size == 0:
        return
    pre = samples.astype(np.float32, copy=True)
    delay_a = int(SAMPLE_RATE * 0.187)
    delay_b = int(SAMPLE_RATE * 0.375)
    if delay_a < samples.shape[0]:
        tap = pre[:-delay_a] * 0.075
        samples[delay_a:, 0] += tap[:, 1]
        samples[delay_a:, 1] += tap[:, 0]
    if delay_b < samples.shape[0]:
        tap = pre[:-delay_b] * 0.042
        samples[delay_b:] += tap
    room = int(SAMPLE_RATE * 0.052)
    if room < samples.shape[0]:
        samples[room:] += samples[:-room] * 0.018
    low = _box_filter(samples, 251)
    bright = samples - _box_filter(samples, 19)
    samples[:] = samples * 0.94 + bright * 0.045 - low * 0.012
    if samples.shape[1] >= 2:
        mid = (samples[:, 0] + samples[:, 1]) * 0.5
        side = (samples[:, 0] - samples[:, 1]) * 0.5 * 1.14
        samples[:, 0] = mid + side
        samples[:, 1] = mid - side
    comp = np.tanh(samples * 1.62) / 1.62
    samples[:] = samples * 0.66 + comp * 0.34
    _normalize_mix(samples, target_peak=0.88, target_rms=0.082)


def _render_studio_edm_preview(
    composition: MusicComposition,
    *,
    output_dir: Path,
    requested_backend: str,
    render_stems: bool = True,
) -> dict[str, Any]:
    import numpy as np

    out = output_dir
    length = max(1, int(math.ceil((composition.duration_ms + 2500) / 1000.0 * SAMPLE_RATE)))
    mix = np.zeros((length, 2), dtype=np.float32)
    stems: dict[str, str] = {}
    for track in composition.tracks:
        samples = np.zeros((length, 2), dtype=np.float32)
        for clip in track.clips:
            for note in clip.notes:
                _render_studio_edm_note(samples, note, bpm=composition.bpm, role=track.role, volume=track.volume, pan=track.pan)
        if _role_family(track.role) not in {"drums", "fx"}:
            _apply_edm_sidechain(samples, bpm=composition.bpm, amount=0.30 if track.role == "bass" else 0.42)
        samples[:] = _box_filter(samples, 3) * 0.34 + samples * 0.66
        if render_stems:
            path = out / f"{composition.id}_{track.role}.wav"
            stem = samples.copy()
            _studio_edm_bus(stem)
            _write_wav(path, stem)
            stems[track.role] = str(path)
        mix += samples
    _studio_edm_bus(mix)
    mix_path = out / f"{composition.id}_mix.wav"
    _write_wav(mix_path, mix)
    composition.rendered_stems = stems
    composition.preview_mix_path = str(mix_path)
    composition.render_engine = "tigerstudio.studio_edm.v1"
    composition.render_backend = {
        "backend": "studio_edm",
        "requested_backend": requested_backend,
        "render_stems": bool(render_stems),
        "quality_tier": MUSIC_QUALITY_DRAFT,
        "production_ready": False,
        "quality_warning": "Draft synth preview only; useful for timing and arrangement, not final music.",
    }
    return {
        "composition_id": composition.id,
        "output_dir": str(out),
        "stems": dict(stems),
        "preview_mix_path": str(mix_path),
        "render_engine": composition.render_engine,
        "render_backend": dict(composition.render_backend),
    }


def _render_local_preview(
    composition: MusicComposition,
    *,
    output_dir: Path,
    requested_backend: str,
    fallback_reason: str = "",
    render_stems: bool = True,
) -> dict[str, Any]:
    import numpy as np

    out = output_dir
    length = max(1, int(math.ceil(composition.duration_ms / 1000.0 * SAMPLE_RATE)))
    mix = np.zeros((length, 2), dtype=np.float32)
    stems: dict[str, str] = {}
    for track in composition.tracks:
        samples = np.zeros((length, 2), dtype=np.float32)
        for clip in track.clips:
            for note in clip.notes:
                _render_note_tone(samples, note, bpm=composition.bpm, role=track.role, volume=track.volume, pan=track.pan)
        path = out / f"{composition.id}_{track.role}.wav"
        _shape_stem(track.role, samples)
        _polish_stereo(samples)
        if render_stems:
            _write_wav(path, samples)
            stems[track.role] = str(path)
        mix += samples
    mix_path = out / f"{composition.id}_mix.wav"
    if composition.tracks:
        mix *= min(1.0, 3.2 / math.sqrt(max(1.0, float(len(composition.tracks)))))
    _polish_stereo(mix, master=True)
    _normalize_preview_mix(mix)
    _write_wav(mix_path, mix)
    composition.rendered_stems = stems
    composition.preview_mix_path = str(mix_path)
    composition.render_engine = "tigerstudio.local_synth.v5"
    composition.render_backend = {
        "backend": "local_synth",
        "requested_backend": requested_backend,
        "fallback_reason": fallback_reason,
        "render_stems": bool(render_stems),
        "quality_tier": MUSIC_QUALITY_DRAFT,
        "production_ready": False,
        "quality_warning": "Draft local synth preview only; not final music.",
    }
    return {
        "composition_id": composition.id,
        "output_dir": str(out),
        "stems": dict(stems),
        "preview_mix_path": str(mix_path),
        "render_engine": composition.render_engine,
        "render_backend": dict(composition.render_backend),
        "fallback_reason": fallback_reason,
    }


def render_preview(
    composition: MusicComposition,
    output_dir: Path | str | None = None,
    *,
    backend: str = "auto",
    soundfont_path: str | Path | None = None,
    render_stems: bool = True,
) -> dict[str, Any]:
    out = Path(output_dir) if output_dir else default_music_render_dir()
    out.mkdir(parents=True, exist_ok=True)
    requested = str(backend or "auto").strip().lower()
    production_status = music_production_renderer_status()
    if requested in {"production", "production_external", "external_music", "external_ai"} or (
        requested == "auto" and production_status.get("ready") and not render_stems
    ):
        return _render_external_production_preview(
            composition,
            output_dir=out,
            requested_backend=requested,
            render_stems=bool(render_stems),
        )
    if requested in {"studio_edm", "edm_studio", "edm", "draft_synth"}:
        return _render_studio_edm_preview(
            composition,
            output_dir=out,
            requested_backend=requested,
            render_stems=bool(render_stems),
        )
    if requested in {"auto", "soundfont", "fluidsynth", "fluidsynth_soundfont"}:
        selected_soundfont = _select_soundfont(soundfont_path)
        fluidsynth_path = find_fluidsynth_executable()
        if selected_soundfont is not None and fluidsynth_path:
            return _render_soundfont_preview(
                composition,
                output_dir=out,
                soundfont_path=selected_soundfont,
                fluidsynth_path=fluidsynth_path,
                render_stems=bool(render_stems),
            )
        if requested != "auto":
            missing = []
            if selected_soundfont is None:
                missing.append("SoundFont")
            if not fluidsynth_path:
                missing.append("FluidSynth")
            raise RuntimeError(f"SoundFont rendering requires: {', '.join(missing)}")
        if _composition_is_melodic_edm(composition):
            return _render_studio_edm_preview(
                composition,
                output_dir=out,
                requested_backend=requested,
                render_stems=bool(render_stems),
            )
        reason = "SoundFont/FluidSynth backend is not ready; using local synth v5."
        return _render_local_preview(
            composition,
            output_dir=out,
            requested_backend=requested,
            fallback_reason=reason,
            render_stems=bool(render_stems),
        )
    return _render_local_preview(composition, output_dir=out, requested_backend=requested, render_stems=bool(render_stems))


def _midi_vlq(value: int) -> bytes:
    raw = max(0, int(value))
    out = [raw & 0x7F]
    raw >>= 7
    while raw:
        out.insert(0, (raw & 0x7F) | 0x80)
        raw >>= 7
    return bytes(out)


def _midi_meta(delta: int, meta_type: int, payload: bytes) -> bytes:
    return _midi_vlq(delta) + bytes((0xFF, int(meta_type) & 0x7F)) + _midi_vlq(len(payload)) + payload


def _midi_chunk(kind: bytes, payload: bytes) -> bytes:
    return kind + struct.pack(">I", len(payload)) + payload


def _midi_track_payload(events: list[tuple[int, int, bytes]], *, end_tick: int = 0) -> bytes:
    payload = bytearray()
    last_tick = 0
    for tick, _priority, data in sorted(events, key=lambda row: (max(0, row[0]), row[1])):
        safe_tick = max(0, int(tick))
        payload += _midi_vlq(max(0, safe_tick - last_tick))
        payload += data
        last_tick = safe_tick
    payload += _midi_vlq(max(0, int(end_tick) - last_tick))
    payload += b"\xff\x2f\x00"
    return bytes(payload)


def _midi_program_for_role(role: str) -> int:
    family = _role_family(role)
    role_text = str(role or "").lower()
    direct = {
        "bass": 38,
        "bass_pulse": 39,
        "bass_layer": 39,
        "sub_bass": 38,
        "chords": 89,
        "pad": 89,
        "arp": 87,
        "melody": 81,
        "lead_answer": 80,
        "lead_harmony": 80,
        "counter": 88,
        "counter_melody": 88,
        "fx": 96,
        "lead": 80,
    }
    if role_text in direct:
        return direct[role_text]
    if role_text.startswith("violins_"):
        return 40
    if role_text.startswith("violas_"):
        return 41
    if role_text.startswith("cellos_"):
        return 42
    if role_text.startswith("contrabasses_"):
        return 43
    if role_text.startswith("timpani_"):
        return 47
    if role_text.startswith("flutes_"):
        return 73
    if role_text.startswith("oboes_"):
        return 68
    if role_text.startswith("clarinets_"):
        return 71
    if role_text.startswith("bassoons_"):
        return 70
    if role_text.startswith("horns_"):
        return 60
    if role_text.startswith(("trumpets_", "trombones_", "low_brass_")):
        return 61
    if role_text.startswith("choir_"):
        return 52
    return {
        "bass": 38,
        "chords": 89,
        "pad": 89,
        "melody": 81,
        "fx": 96,
        "lead": 80,
        "strings_low": 43,
        "strings_mid": 41,
        "strings_high": 40,
        "woodwinds": 73,
        "brass": 60,
        "choir": 52,
        "timpani": 47,
    }.get(family, 88)


def _midi_channel_controllers_for_track(track: MusicTrack) -> list[tuple[int, int]]:
    family = _role_family(track.role)
    role_text = str(track.role or "").lower()
    volume = max(0.0, min(1.2, float(track.volume or 0.8)))
    pan = max(-1.0, min(1.0, float(track.pan or 0.0)))
    volume_cc = max(18, min(118, int(round(volume * 104.0))))
    pan_cc = max(0, min(127, int(round(64.0 + pan * 52.0))))
    reverb = 24
    chorus = 10
    expression = 112
    if family in {"drums", "orchestral_percussion"}:
        reverb = 18
        chorus = 4
        expression = 118
    elif family == "bass":
        reverb = 10
        chorus = 8 if role_text.startswith("bass_pulse") else 3
        expression = 116
    elif family in {"chords", "pad", "choir"}:
        reverb = 48
        chorus = 34
        expression = 108
    elif family == "melody":
        reverb = 34
        chorus = 24
        expression = 112
    elif family in {"strings_mid", "strings_high", "woodwinds"}:
        reverb = 44
        chorus = 18
        expression = 110
    elif family in {"strings_low", "brass", "timpani"}:
        reverb = 32
        chorus = 10
        expression = 112
    elif family == "fx":
        reverb = 58
        chorus = 28
        expression = 104
    return [
        (7, volume_cc),
        (10, pan_cc),
        (11, expression),
        (91, reverb),
        (93, chorus),
    ]


def export_midi(
    composition: MusicComposition,
    *,
    output_path: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    out = Path(output_path) if output_path else (Path(output_dir) if output_dir else default_music_render_dir()) / f"{composition.id}.mid"
    out.parent.mkdir(parents=True, exist_ok=True)
    tempo_us = int(round(60000000.0 / max(1, composition.bpm)))
    title = f"TigerCapture Music Lab - {composition.prompt}".encode("utf-8", errors="replace")[:120]
    tempo_events = [
        (0, 0, b"\xff\x03" + _midi_vlq(len(title)) + title),
        (0, 1, b"\xff\x51\x03" + tempo_us.to_bytes(3, "big")),
        (0, 2, b"\xff\x58\x04\x04\x02\x18\x08"),
    ]
    chunks = [_midi_chunk(b"MTrk", _midi_track_payload(tempo_events, end_tick=0))]

    channel = 0
    note_count = 0
    for track in composition.tracks:
        role = str(track.role or track.id or "track").lower()
        family = _role_family(role)
        percussion_channel = family in {"drums", "orchestral_percussion"} or role.startswith("cymbals_fx_")
        midi_channel = 9 if percussion_channel else channel
        if not percussion_channel:
            channel += 1
            if channel == 9:
                channel += 1
            channel = min(channel, 15)
        name = f"{track.role} - {track.instrument}".encode("utf-8", errors="replace")[:80]
        events: list[tuple[int, int, bytes]] = [
            (0, 0, b"\xff\x03" + _midi_vlq(len(name)) + name),
        ]
        if not percussion_channel:
            events.append((0, 1, bytes((0xC0 | midi_channel, _midi_program_for_role(role)))))
        for controller, value in _midi_channel_controllers_for_track(track):
            events.append((0, 2, bytes((0xB0 | midi_channel, int(controller), int(value)))))
        end_tick = 0
        for clip in track.clips:
            for note in clip.notes:
                pitch = max(0, min(127, int(note.pitch)))
                velocity = max(1, min(127, int(note.velocity)))
                start_tick = max(0, int(note.start_tick))
                end = max(start_tick + 1, start_tick + int(note.duration_tick))
                events.append((start_tick, 10, bytes((0x90 | midi_channel, pitch, velocity))))
                events.append((end, 0, bytes((0x80 | midi_channel, pitch, 0))))
                end_tick = max(end_tick, end)
                note_count += 1
        chunks.append(_midi_chunk(b"MTrk", _midi_track_payload(events, end_tick=end_tick)))

    header = _midi_chunk(b"MThd", struct.pack(">HHH", 1, len(chunks), int(composition.ticks_per_beat or TICKS_PER_BEAT)))
    payload = header + b"".join(chunks)
    out.write_bytes(payload)
    return {
        "composition_id": composition.id,
        "path": str(out),
        "track_count": len(composition.tracks),
        "note_count": note_count,
        "ticks_per_beat": int(composition.ticks_per_beat or TICKS_PER_BEAT),
        "bytes": len(payload),
    }


def summary(composition: MusicComposition) -> dict[str, Any]:
    return {
        "id": composition.id,
        "prompt": composition.prompt,
        "genre": composition.genre,
        "mood": composition.mood,
        "bpm": composition.bpm,
        "key": composition.key,
        "duration_ms": composition.duration_ms,
        "section_count": len(composition.sections),
        "track_count": len(composition.tracks),
        "note_count": sum(len(clip.notes) for track in composition.tracks for clip in track.clips),
        "rendered": bool(composition.rendered_stems),
        "preview_mix_path": composition.preview_mix_path,
        "render_engine": composition.render_engine,
        "render_backend": dict(composition.render_backend or {}),
    }
