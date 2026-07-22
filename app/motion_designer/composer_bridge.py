"""Structured Music Composer timing bridge for Motion Designer."""
from __future__ import annotations

from typing import Any, Mapping

from app.music_composer import MusicComposition, composition_from_dict

from .schema import MotionComposition, new_motion_id


TIMING_SOURCES_KEY = "audio_timing_sources"


def _music_composition(value: MusicComposition | Mapping[str, Any]) -> MusicComposition:
    if isinstance(value, MusicComposition):
        return value
    return composition_from_dict(dict(value))


def composer_timing_source(value: MusicComposition | Mapping[str, Any], *, timeline_start_ms: int = 0,
                           source_id: str = "") -> dict[str, Any]:
    music = _music_composition(value)
    start = max(0, int(timeline_start_ms))
    bpm = max(1, int(music.bpm))
    beat_span = 60000.0 / bpm
    beat_markers: list[int] = []
    cursor = 0.0
    while cursor <= max(0, music.duration_ms):
        beat_markers.append(start + int(round(cursor)))
        cursor += beat_span
    sections = [{
        "kind": "section", "name": section.name,
        "start_ms": start + int(section.start_ms),
        "end_ms": start + int(section.start_ms + section.duration_ms),
        "intensity": float(section.intensity),
        "chord_progression": list(section.chord_progression),
    } for section in music.sections]
    note_events: list[dict[str, Any]] = []
    tick_ms = beat_span / max(1, int(music.ticks_per_beat))
    for track in music.tracks:
        for clip in track.clips:
            for note in clip.notes:
                note_start = start + int(clip.start_ms) + int(round(note.start_tick * tick_ms))
                note_events.append({
                    "kind": "note", "track_id": track.id, "role": track.role,
                    "instrument": track.instrument, "clip_id": clip.id,
                    "section_name": clip.section_name, "pitch": int(note.pitch),
                    "velocity": int(note.velocity), "start_ms": note_start,
                    "end_ms": note_start + max(1, int(round(note.duration_tick * tick_ms))),
                })
    note_events.sort(key=lambda row: (row["start_ms"], row["track_id"], row["pitch"]))
    return {
        "id": str(source_id or new_motion_id("composer_timing")),
        "kind": "composer", "priority": 100, "structured": True,
        "source_composition_id": music.id, "timeline_start_ms": start,
        "duration_ms": int(music.duration_ms), "bpm": bpm,
        "beat_markers": beat_markers, "sections": sections, "note_events": note_events,
        "audio_path": str(music.preview_mix_path or ""),
        "metadata": {"schema": "tigerstudio.motion.composer_timing.v1", "key": music.key,
                     "genre": music.genre, "mood": music.mood},
    }


def import_composer_timing(composition: MotionComposition, value: MusicComposition | Mapping[str, Any],
                           *, timeline_start_ms: int = 0, source_id: str = "") -> dict[str, Any]:
    timing = composer_timing_source(value, timeline_start_ms=timeline_start_ms, source_id=source_id)
    sources = dict(composition.metadata.get(TIMING_SOURCES_KEY) or {})
    sources[timing["id"]] = timing
    composition.metadata[TIMING_SOURCES_KEY] = sources
    return timing


def preferred_beat_markers(composition: MotionComposition, analysis: Mapping[str, Any] | None = None) -> list[int]:
    sources = composition.metadata.get(TIMING_SOURCES_KEY) or {}
    structured = sorted(
        (row for row in sources.values() if isinstance(row, Mapping) and row.get("beat_markers")),
        key=lambda row: int(row.get("priority", 0)), reverse=True,
    )
    if structured:
        return [int(value) for value in structured[0].get("beat_markers", [])]
    return [int(value) for value in (analysis or {}).get("beat_markers", [])]


__all__ = ["TIMING_SOURCES_KEY", "composer_timing_source", "import_composer_timing", "preferred_beat_markers"]
