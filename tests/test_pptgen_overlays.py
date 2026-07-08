from __future__ import annotations

from app.pptgen.overlays import header_footer_settings, set_header_footer, slide_overlay_elements
from app.pptgen.schema import DeckSpec


def test_header_footer_settings_round_trip_through_deck_json():
    deck = DeckSpec.sample()
    set_header_footer(
        deck,
        show_header=True,
        header_text="Quarterly Review",
        show_footer=True,
        footer_text="Internal",
        show_date=True,
        date_text="2026-07-06",
        show_slide_number=True,
    )

    restored = DeckSpec.from_json(deck.to_json())

    settings = header_footer_settings(restored)
    assert settings["show_header"] is True
    assert settings["header_text"] == "Quarterly Review"
    assert settings["footer_text"] == "Internal"
    assert settings["date_text"] == "2026-07-06"
    assert settings["show_slide_number"] is True


def test_slide_overlay_elements_include_enabled_repeated_fields():
    deck = DeckSpec.sample()
    set_header_footer(
        deck,
        show_header=True,
        header_text="Deck Header",
        show_footer=True,
        footer_text="Deck Footer",
        show_date=True,
        date_text="2026-07-06",
        show_slide_number=True,
    )

    overlays = slide_overlay_elements(deck, "slide-001", slide_index=2, slide_count=5)
    texts = [element.text for element in overlays]

    assert texts == ["Deck Header", "Deck Footer", "2026-07-06", "2 / 5"]
    assert all(element.locked for element in overlays)
