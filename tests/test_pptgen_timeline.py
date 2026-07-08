from __future__ import annotations

from app.pptgen.schema import DeckSpec
from app.pptgen.timeline import PptTimeline, move_slide


def test_timeline_from_deck_uses_slide_duration_order():
    deck = DeckSpec.sample()

    timeline = PptTimeline.from_deck(deck)

    assert [clip.slide_id for clip in timeline.slide_clips] == [slide.id for slide in deck.slides]
    assert timeline.slide_clips[0].start_ms == 0
    assert timeline.slide_clips[1].start_ms == deck.slides[0].duration_ms


def test_move_slide_rebuilds_timeline_order():
    deck = DeckSpec.sample()

    timeline = move_slide(deck, "slide-003", 0)

    assert deck.slides[0].id == "slide-003"
    assert timeline.slide_clips[0].slide_id == "slide-003"

