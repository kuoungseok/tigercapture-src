"""Rendered locale and font-fallback audit for critical Painter UI copy."""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication

from app.i18n import SUPPORTED_LANGUAGES
from app.painter_i18n import painter_text


SCHEMA = "tigerstudio.painter.ui.locale_audit.v1"
_SUSPICIOUS = re.compile(r"\ufffd|(?:Ã.|Â.)")

DEFAULT_CORPUS: tuple[dict[str, Any], ...] = (
    {"id": "tab.design", "text": "Design", "width": 92},
    {"id": "tab.prototype", "text": "Prototype", "width": 104},
    {"id": "tab.inspect", "text": "Inspect", "width": 86},
    {"id": "mode.ui", "text": "UI Design", "width": 110},
    {"id": "menu.find", "text": "Find / Replace", "width": 168},
    {"id": "menu.rename", "text": "Batch Rename", "width": 168},
    {
        "id": "menu.shortcuts",
        "text": "Keyboard shortcuts",
        "width": 190,
    },
    {
        "id": "menu.parity",
        "text": "UI / Action parity",
        "width": 190,
    },
    {
        "id": "menu.focus_audit",
        "text": "Keyboard focus audit",
        "width": 190,
    },
    {"id": "status.covered", "text": "Covered", "width": 92},
    {
        "id": "family.design_system",
        "text": "Components, variables and styles",
        "width": 210,
        "allow_elide": True,
    },
    {
        "id": "surface.layout",
        "text": "Design > Layout / responsive preview",
        "width": 260,
        "allow_elide": True,
    },
)


def inspect_painter_ui_locales(
    corpus: Iterable[Mapping[str, Any]] | None = None,
    *,
    languages: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Measure translated critical copy with the active application font."""

    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Painter locale audit requires QApplication")
    metrics = QFontMetrics(app.font())
    requested = [
        str(value)
        for value in (languages or SUPPORTED_LANGUAGES.keys())
        if str(value) in SUPPORTED_LANGUAGES
    ]
    rows = [dict(row) for row in (corpus or DEFAULT_CORPUS)]
    locale_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    for language in requested:
        overflow_count = 0
        elided_count = 0
        missing_glyph_count = 0
        corrupt_count = 0
        maximum_ratio = 0.0
        for row in rows:
            translated = painter_text(str(row.get("text") or ""), language)
            budget = max(1, int(row.get("width") or 1))
            measured = metrics.horizontalAdvance(translated)
            ratio = measured / budget
            maximum_ratio = max(maximum_ratio, ratio)
            missing = sorted(
                {
                    character
                    for character in translated
                    if not character.isspace()
                    and not metrics.inFontUcs4(ord(character))
                }
            )
            corrupt = bool(_SUSPICIOUS.search(translated))
            over = measured > budget
            allow_elide = bool(row.get("allow_elide"))
            if over and allow_elide:
                elided_count += 1
            elif over:
                overflow_count += 1
            missing_glyph_count += len(missing)
            corrupt_count += int(corrupt)
            if (over and not allow_elide) or missing or corrupt:
                issue_rows.append(
                    {
                        "language": language,
                        "id": str(row.get("id") or ""),
                        "text": translated,
                        "width_budget": budget,
                        "measured_width": measured,
                        "missing_glyphs": missing,
                        "corrupt": corrupt,
                        "reason": (
                            "missing_glyph"
                            if missing
                            else "corrupt_text"
                            if corrupt
                            else "overflow"
                        ),
                    }
                )
        locale_rows.append(
            {
                "language": language,
                "label": SUPPORTED_LANGUAGES[language],
                "entry_count": len(rows),
                "overflow_count": overflow_count,
                "elided_count": elided_count,
                "missing_glyph_count": missing_glyph_count,
                "corrupt_count": corrupt_count,
                "maximum_width_ratio": round(maximum_ratio, 3),
                "status": (
                    "blocked"
                    if overflow_count or missing_glyph_count or corrupt_count
                    else "covered"
                ),
            }
        )
    return {
        "schema": SCHEMA,
        "font_family": app.font().family(),
        "language_count": len(locale_rows),
        "entry_count": len(rows),
        "status": "blocked" if issue_rows else "covered",
        "issue_count": len(issue_rows),
        "locales": locale_rows,
        "issues": issue_rows,
    }


__all__ = ["DEFAULT_CORPUS", "SCHEMA", "inspect_painter_ui_locales"]
