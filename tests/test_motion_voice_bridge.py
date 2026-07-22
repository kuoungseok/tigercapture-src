from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.voice_bridge import import_voice_timing, voice_timing_source


def test_voice_bridge_uses_explicit_timing_and_estimates_missing_words() -> None:
    timing = voice_timing_source([
        {"start_ms": 0, "end_ms": 1000, "text": "Hello Tiger",
         "words": [{"text": "Hello", "start_ms": 0, "end_ms": 420},
                   {"text": "Tiger", "start_ms": 420, "end_ms": 1000}]},
        {"start_ms": 1200, "end_ms": 2200, "display_text": "Motion Studio"},
    ], timeline_start_ms=500)
    assert timing["sentences"][0]["start_ms"] == 500
    assert timing["words"][0]["start_ms"] == 500
    estimated = [row for row in timing["words"] if row.get("sentence_index") == 1]
    assert len(estimated) == 2 and all(row["estimated"] for row in estimated)


def test_voice_bridge_attaches_text_reveal_and_actor_lip_sync() -> None:
    text = MotionLayer(name="Subtitle", layer_type="text", source=SourceRef(kind="typography", params={"text": "Hi"}))
    actor = MotionLayer(name="Actor", layer_type="live2d", source=SourceRef(kind="live2d"))
    composition = MotionComposition(layers=[text, actor])
    timing = import_voice_timing(composition, [{
        "start_ms": 100, "end_ms": 600, "text": "Hi",
        "phonemes": [{"phoneme": "a", "start_ms": 120, "end_ms": 300}],
    }], text_layer=text, actor_layer=actor)
    assert text.source.params["text_reveal_timing"]["source_id"] == timing["id"]
    assert actor.metadata["lip_sync_cues"][0]["text"] == "a"
    assert composition.metadata["audio_timing_sources"][timing["id"]]["kind"] == "voice"
