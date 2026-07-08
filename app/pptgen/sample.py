"""Sample deck helpers for the PPT generator."""
from __future__ import annotations

from app.pptgen.schema import DeckSpec


def create_sample_deck() -> DeckSpec:
    return DeckSpec.sample()


__all__ = ["create_sample_deck"]
