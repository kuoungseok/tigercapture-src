"""Phase 5 Step A: Overlay layer model.

Subtitles and typography are conceptually *project-level overlays* —
they float above whatever video is playing. The current code stores
typography per-track (``track.typography_actors``) and subtitles
inside the ``SubtitlePanel`` view. That's expedient but ties the
data to the UI / track structure, which makes it hard to:

- Show subtitle markers on the timeline ruler (Step A's visible win)
- Drag subtitles on a timeline lane (Step B)
- Survive track deletion / reassignment with overlays intact

This module factors the storage out into two thin layer classes:

- ``SubtitleLayer`` — owns ``list[Subtitle]`` + lookup
- ``TypographyLayer`` — same shape, owns ``list[TextClip]``

The classes are deliberately tiny (no Qt) so they're safe to import
anywhere and unit-test headless. ``SubtitlePanel`` keeps a layer
internally and acts as its UI binding; the editor reads the layer
directly for the preview-overlay update + timeline-ruler markers.
"""
from __future__ import annotations

from typing import Callable, Generic, Iterable, Optional, TypeVar


T = TypeVar("T")


class _OverlayLayer(Generic[T]):
    """Base list-of-time-ranges container with ``active_at`` lookup.

    ``T`` items must expose ``start_ms`` / ``end_ms`` integer fields
    (duck-typed). The class doesn't impose any storage shape beyond
    that, so both ``Subtitle`` (text) and ``TextClip`` (typography)
    fit without modification.
    """

    def __init__(self, items: Optional[Iterable[T]] = None) -> None:
        self._items: list[T] = list(items or [])
        self._sort_inplace()
        # Hook fired after every mutation. Editors register here so a
        # repaint kicks in without each call site needing to remember.
        self.on_change: Optional[Callable[[], None]] = None

    # ---- read ----

    def items(self) -> list[T]:
        return list(self._items)

    def __iter__(self):
        return iter(list(self._items))

    def __len__(self) -> int:
        return len(self._items)

    def active_at(self, pos_ms: int) -> list[T]:
        """All items whose ``[start_ms, end_ms)`` contains ``pos_ms``.
        Multiple items can be active at once (e.g. a translation
        subtitle plus a description), so the return is a list rather
        than a single item."""
        return [
            it for it in self._items
            if int(getattr(it, "start_ms", 0)) <= int(pos_ms) < int(getattr(it, "end_ms", 0))
        ]

    def first_active_at(self, pos_ms: int) -> Optional[T]:
        """Convenience wrapper for the common single-overlay case
        (the existing subtitle preview overlay shows one item at a
        time). Returns the earliest-starting active item, or None."""
        for it in self._items:
            if int(getattr(it, "start_ms", 0)) <= int(pos_ms) < int(getattr(it, "end_ms", 0)):
                return it
        return None

    # ---- write ----

    def add(self, item: T) -> None:
        self._items.append(item)
        self._sort_inplace()
        self._fire_change()

    def remove(self, item: T) -> bool:
        try:
            self._items.remove(item)
        except ValueError:
            return False
        self._fire_change()
        return True

    def replace_at(self, idx: int, item: T) -> None:
        if 0 <= idx < len(self._items):
            self._items[idx] = item
            self._sort_inplace()
            self._fire_change()

    def clear(self) -> None:
        if not self._items:
            return
        self._items.clear()
        self._fire_change()

    def replace_all(self, items: Iterable[T]) -> None:
        """Bulk replace — used by import / SRT load paths and tests."""
        self._items = list(items)
        self._sort_inplace()
        self._fire_change()

    def _sort_inplace(self) -> None:
        self._items.sort(key=lambda it: int(getattr(it, "start_ms", 0)))

    def _fire_change(self) -> None:
        if self.on_change is not None:
            try:
                self.on_change()
            except Exception:
                # A misbehaving listener must not corrupt the layer
                # state — swallow and continue.
                pass


class SubtitleLayer(_OverlayLayer):
    """Project-level subtitle layer. Holds ``list[Subtitle]`` ordered
    by ``start_ms``. The ``SubtitlePanel`` is the editor-side UI
    binding; the editor's preview overlay and the timeline ruler's
    marker strip both read from this same instance."""


class TypographyLayer(_OverlayLayer):
    """Project-level typography layer. Phase 5 Step A: parallel to
    ``SubtitleLayer`` but not yet wired through the editor — the
    legacy ``track.typography_actors`` storage stays canonical for
    now. Step B will migrate per-track typography into this layer
    (lifting actors out of tracks they happen to be parked on)."""
