from __future__ import annotations


def test_deck_from_prompt_builds_editable_slides():
    from app.pptgen.prompt_deck import deck_from_prompt

    deck = deck_from_prompt(
        "Launch Plan\nAudience fit\nDemo flow\nQA checklist\nRelease",
        title="Launch Plan",
        max_slides=2,
    )

    assert deck.title == "Launch Plan"
    assert deck.metadata["source"] == "prompt"
    assert len(deck.slides) == 1
    text = "\n".join(element.text for slide in deck.slides for element in slide.elements if element.text)
    assert "Audience fit" in text
    assert "Demo flow" in text


def test_deck_from_prompt_can_split_long_prompt():
    from app.pptgen.prompt_deck import deck_from_prompt

    lines = ["Roadmap"] + [f"Point {index}" for index in range(1, 14)]
    deck = deck_from_prompt("\n".join(lines), title="Roadmap", max_slides=3)

    assert len(deck.slides) == 3
    assert deck.slides[1].metadata["source"] == "prompt"
