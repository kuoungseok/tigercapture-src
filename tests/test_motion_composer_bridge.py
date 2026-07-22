from app.motion_designer.composer_bridge import import_composer_timing, preferred_beat_markers
from app.motion_designer.schema import MotionComposition
from app.music_composer import MidiClip, MidiNote, MusicComposition, MusicSection, MusicTrack


def test_composer_bridge_preserves_structured_beats_sections_and_notes() -> None:
    music = MusicComposition(
        id="music_demo", prompt="", genre="pop", mood="bright", bpm=120, key="C",
        duration_ms=2000, ticks_per_beat=480,
        sections=[MusicSection("Intro", 0, 1000, 0.5, ["C", "G"])],
        tracks=[MusicTrack("lead", "lead", "synth", clips=[
            MidiClip("clip", "Intro", 250, 1000, [MidiNote(60, 240, 480, 100)]),
        ])],
    )
    composition = MotionComposition(duration_ms=4000)
    timing = import_composer_timing(composition, music, timeline_start_ms=1000)
    assert timing["beat_markers"][:3] == [1000, 1500, 2000]
    assert timing["sections"][0]["start_ms"] == 1000
    assert timing["note_events"][0]["start_ms"] == 1500
    assert timing["note_events"][0]["end_ms"] == 2000
    assert preferred_beat_markers(composition, {"beat_markers": [7, 8]})[:2] == [1000, 1500]
