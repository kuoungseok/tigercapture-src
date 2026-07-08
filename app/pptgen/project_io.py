"""Project-file IO for the user PPT generator."""
from __future__ import annotations

from pathlib import Path

from app.pptgen.schema import DeckSpec


PPTGEN_PROJECT_EXTENSION = ".tgppt"
PPTGEN_PROJECT_FILTER = "TigerCapture PPT Project (*.tgppt);;JSON (*.json)"


def save_deck_project(deck: DeckSpec, path: str | Path) -> Path:
    target = Path(path)
    if not target.suffix:
        target = target.with_suffix(PPTGEN_PROJECT_EXTENSION)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(deck.to_json(indent=2), encoding="utf-8")
    return target


def load_deck_project(path: str | Path) -> DeckSpec:
    source = Path(path)
    return DeckSpec.from_json(source.read_text(encoding="utf-8"))


__all__ = [
    "PPTGEN_PROJECT_EXTENSION",
    "PPTGEN_PROJECT_FILTER",
    "load_deck_project",
    "save_deck_project",
]
