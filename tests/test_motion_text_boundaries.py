from __future__ import annotations

from app.motion_designer.text_boundaries import (
    QtTextBoundaryProvider,
    unicode_grapheme_spans,
)


def _segments(text: str) -> list[str]:
    return [text[span.start:span.end] for span in unicode_grapheme_spans(text)]


def test_unicode_graphemes_keep_flags_modifiers_and_zwj_sequences_together() -> None:
    assert _segments("🇰🇷") == ["🇰🇷"]
    assert _segments("👍🏽") == ["👍🏽"]
    assert _segments("👨‍👩‍👧‍👦") == ["👨‍👩‍👧‍👦"]


def test_unicode_graphemes_keep_combining_marks_and_hangul_jamo_together() -> None:
    assert _segments("e\u0301") == ["e\u0301"]
    assert _segments("한") == ["한"]


def test_unicode_grapheme_offsets_use_python_indices_not_utf16_offsets() -> None:
    text = "A👍🏽B"
    spans = unicode_grapheme_spans(text)
    assert [(span.start, span.end) for span in spans] == [(0, 1), (1, 3), (3, 4)]


def test_boundary_provider_cache_is_bounded() -> None:
    provider = QtTextBoundaryProvider()
    for index in range(600):
        provider.grapheme_spans(f"row {index} 👍🏽")
    info = provider._cached_grapheme_spans.cache_info()
    assert info.maxsize == 512
    assert info.currsize <= 512
