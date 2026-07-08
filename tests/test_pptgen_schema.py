from __future__ import annotations

from app.pptgen.schema import DeckSpec, SlideElement


def test_deck_spec_json_round_trip_keeps_slides_and_elements():
    deck = DeckSpec.sample()
    deck.slides[0].elements[0].style.font_family = "Georgia"
    deck.slides[0].elements[0].style.italic = True
    deck.slides[0].elements[0].style.underline = True
    deck.slides[0].elements[0].style.line_height = 1.35
    deck.slides[0].elements[0].animation.in_animation = "fade_in"
    deck.slides[0].elements[0].animation.start_ms = 250
    deck.slides[0].elements[0].animation.duration_ms = 650

    restored = DeckSpec.from_json(deck.to_json())

    assert restored.title == deck.title
    assert len(restored.slides) == 3
    assert restored.slides[0].elements[0].text.startswith("Timeline-native")
    assert restored.slides[0].elements[0].style.font_family == "Georgia"
    assert restored.slides[0].elements[0].style.italic is True
    assert restored.slides[0].elements[0].style.underline is True
    assert restored.slides[0].elements[0].style.line_height == 1.35
    assert restored.slides[0].elements[0].animation.in_animation == "fade_in"
    assert restored.slides[0].elements[0].animation.start_ms == 250
    assert restored.slides[0].elements[0].animation.duration_ms == 650
    assert restored.theme.background == "#FFFFFF"
    assert restored.theme.ink == "#182033"
    assert restored.theme.accent == "#2F6FED"


def test_document_tool_elements_round_trip():
    deck = DeckSpec.sample()
    slide = deck.slides[0]
    slide.add_element(SlideElement.table("table-1", x=0.1, y=0.2, w=0.4, h=0.3, rows=4, cols=3))
    slide.add_element(SlideElement.chart("chart-1", x=0.5, y=0.2, w=0.3, h=0.3))
    slide.add_element(SlideElement.line("line-1", x=0.12, y=0.72, w=0.5, h=0.03))

    restored = DeckSpec.from_json(deck.to_json())
    kinds = {element.kind for element in restored.slides[0].elements}

    assert {"table", "chart", "line"}.issubset(kinds)
    table = next(element for element in restored.slides[0].elements if element.kind == "table")
    assert table.metadata["rows"] == 4
    assert table.metadata["cols"] == 3
