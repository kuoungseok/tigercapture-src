"""Prompt-to-deck helpers for the user PPT generator."""
from __future__ import annotations

from app.pptgen.schema import DeckSpec, SlideElement
from app.pptgen.templates import deck_from_template, slide_from_template, template_by_id


def _clean_lines(text: str) -> list[str]:
    return [line.strip(" \t-*#") for line in str(text or "").splitlines() if line.strip(" \t-*#")]


def _derive_title(prompt: str) -> str:
    lines = _clean_lines(prompt)
    if not lines:
        return "Prompt Deck"
    title = lines[0]
    return title[:80].strip() or "Prompt Deck"


def _text_elements(deck: DeckSpec) -> list[SlideElement]:
    return [element for slide in deck.slides for element in slide.elements if element.kind in {"text", "typography_actor"}]


def _set_slot_text(deck: DeckSpec, slot: str, text: str) -> bool:
    for slide in deck.slides:
        for element in slide.elements:
            if element.metadata.get("slot") == slot and element.kind in {"text", "typography_actor"}:
                element.text = text
                return True
    return False


def deck_from_prompt(
    prompt: str,
    *,
    title: str = "",
    template_id: str = "title_body",
    max_slides: int = 4,
) -> DeckSpec:
    """Build a deterministic editable deck from a short user prompt.

    This is intentionally conservative. It gives automation a real project
    surface without pretending to be a full generative design engine.
    """

    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        raise ValueError("prompt is required")
    safe_template_id = template_id if template_by_id(template_id) is not None else "title_body"
    deck_title = str(title or "").strip() or _derive_title(clean_prompt)
    deck = deck_from_template(safe_template_id, deck_id="prompt-deck", title=deck_title)
    deck.metadata["prompt"] = clean_prompt
    deck.metadata["source"] = "prompt"

    lines = _clean_lines(clean_prompt)
    body_lines = lines[1:] if len(lines) > 1 else lines
    body = "\n".join(f"- {line}" for line in body_lines[:6]) or clean_prompt[:420]
    if not _set_slot_text(deck, "title", deck_title):
        texts = _text_elements(deck)
        if texts:
            texts[0].text = deck_title
    if not _set_slot_text(deck, "body", body):
        texts = _text_elements(deck)
        if len(texts) > 1:
            texts[1].text = body

    remaining = body_lines[6:]
    slide_limit = max(1, int(max_slides or 4))
    slide_number = 2
    while remaining and len(deck.slides) < slide_limit:
        chunk = remaining[:6]
        remaining = remaining[6:]
        slide = slide_from_template("title_body", slide_id=f"slide-{slide_number:03d}", title=f"{deck_title} {slide_number}")
        for element in slide.elements:
            slot = element.metadata.get("slot")
            if slot == "title":
                element.text = f"{deck_title} {slide_number}"
            elif slot == "body":
                element.text = "\n".join(f"- {line}" for line in chunk)
        slide.metadata["source"] = "prompt"
        deck.slides.append(slide)
        slide_number += 1
    return deck


__all__ = ["deck_from_prompt"]
