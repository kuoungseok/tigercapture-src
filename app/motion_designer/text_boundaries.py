"""Unicode text-boundary services shared by typography evaluators."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TextSpan:
    start: int
    end: int


class TextBoundaryUnavailableError(RuntimeError):
    """Raised when no standards-backed grapheme provider is available."""


class TextBoundaryProvider(Protocol):
    provider_id: str

    def grapheme_spans(self, text: str) -> tuple[TextSpan, ...]: ...


def _utf16_boundary_map(text: str) -> dict[int, int]:
    """Map QString UTF-16 offsets to Python code-point offsets."""
    result = {0: 0}
    utf16_offset = 0
    for python_offset, character in enumerate(text, start=1):
        utf16_offset += len(character.encode("utf-16-le")) // 2
        result[utf16_offset] = python_offset
    return result


class QtTextBoundaryProvider:
    """UAX #29 grapheme segmentation supplied by Qt's Unicode engine."""

    provider_id = "qt_qtextboundaryfinder_grapheme_v1"

    @staticmethod
    @lru_cache(maxsize=512)
    def _cached_grapheme_spans(text: str) -> tuple[TextSpan, ...]:
        try:
            from PySide6.QtCore import QTextBoundaryFinder
        except ImportError as exc:  # pragma: no cover - packaged dependency
            raise TextBoundaryUnavailableError(
                "Unicode grapheme segmentation requires PySide6.QtCore."
            ) from exc

        if not text:
            return ()
        finder = QTextBoundaryFinder(QTextBoundaryFinder.Grapheme, text)
        finder.toStart()
        utf16_boundaries = [0, *iter(finder.toNextBoundary, -1)]
        offset_map = _utf16_boundary_map(text)
        try:
            python_boundaries = [offset_map[offset] for offset in utf16_boundaries]
        except KeyError as exc:  # pragma: no cover - defensive Qt contract guard
            raise TextBoundaryUnavailableError(
                f"Qt returned a non-code-point grapheme boundary: {exc.args[0]}"
            ) from exc
        return tuple(
            TextSpan(start, end)
            for start, end in zip(python_boundaries, python_boundaries[1:])
            if end > start
        )

    def grapheme_spans(self, text: str) -> tuple[TextSpan, ...]:
        return self._cached_grapheme_spans(str(text))


DEFAULT_TEXT_BOUNDARY_PROVIDER: TextBoundaryProvider = QtTextBoundaryProvider()


def unicode_grapheme_spans(text: str) -> tuple[TextSpan, ...]:
    return DEFAULT_TEXT_BOUNDARY_PROVIDER.grapheme_spans(text)


__all__ = [
    "DEFAULT_TEXT_BOUNDARY_PROVIDER",
    "QtTextBoundaryProvider",
    "TextBoundaryProvider",
    "TextBoundaryUnavailableError",
    "TextSpan",
    "unicode_grapheme_spans",
]
