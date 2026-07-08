"""Undo/redo snapshots for the user PPT generator.

The stack stores plain deck dictionaries instead of Qt objects. That keeps the
history cheap to compare, safe to deepcopy, and reusable from Actions/tests.
"""
from __future__ import annotations

import copy
from typing import Any

from app.pptgen.schema import DeckSpec


DeckSnapshot = dict[str, Any]


def capture_deck_snapshot(deck: DeckSpec) -> DeckSnapshot:
    """Return an isolated JSON-compatible snapshot for ``deck``."""
    return copy.deepcopy(deck.to_dict())


def deck_from_history_snapshot(snapshot: DeckSnapshot) -> DeckSpec:
    """Restore a ``DeckSpec`` from a snapshot produced by this module."""
    return DeckSpec.from_dict(copy.deepcopy(snapshot))


class PptHistoryStack:
    """Bounded deck-level undo/redo history."""

    def __init__(self, max_undo_steps: int = 50) -> None:
        self._max_entries = max(2, int(max_undo_steps) + 1)
        self._stack: list[tuple[DeckSnapshot, str]] = []
        self._cursor = -1

    def reset(self, deck: DeckSpec, label: str = "Initial") -> None:
        self._stack = [(capture_deck_snapshot(deck), str(label or ""))]
        self._cursor = 0

    def push(self, deck: DeckSpec, label: str = "Edit") -> bool:
        snapshot = capture_deck_snapshot(deck)
        if 0 <= self._cursor < len(self._stack) and self._stack[self._cursor][0] == snapshot:
            return False
        del self._stack[self._cursor + 1 :]
        self._stack.append((snapshot, str(label or "")))
        if len(self._stack) > self._max_entries:
            overflow = len(self._stack) - self._max_entries
            self._stack = self._stack[overflow:]
        self._cursor = len(self._stack) - 1
        return True

    def undo(self) -> DeckSnapshot | None:
        if self._cursor <= 0:
            return None
        self._cursor -= 1
        return copy.deepcopy(self._stack[self._cursor][0])

    def redo(self) -> DeckSnapshot | None:
        if self._cursor >= len(self._stack) - 1:
            return None
        self._cursor += 1
        return copy.deepcopy(self._stack[self._cursor][0])

    def can_undo(self) -> bool:
        return self._cursor > 0

    def can_redo(self) -> bool:
        return self._cursor < len(self._stack) - 1

    def depth(self) -> int:
        return len(self._stack)

    def undo_label(self) -> str:
        if not self.can_undo():
            return ""
        return self._stack[self._cursor][1]

    def redo_label(self) -> str:
        if not self.can_redo():
            return ""
        return self._stack[self._cursor + 1][1]


__all__ = [
    "DeckSnapshot",
    "PptHistoryStack",
    "capture_deck_snapshot",
    "deck_from_history_snapshot",
]
