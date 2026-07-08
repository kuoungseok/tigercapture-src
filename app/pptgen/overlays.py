"""Deck-level slide overlays such as header, footer, date, and slide number."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.pptgen.schema import DeckSpec, SlideElement


HEADER_FOOTER_KEY = "header_footer"


DEFAULT_HEADER_FOOTER: dict[str, Any] = {
    "show_header": False,
    "header_text": "",
    "show_footer": False,
    "footer_text": "",
    "show_date": False,
    "date_text": "",
    "show_slide_number": False,
}


def header_footer_settings(deck: DeckSpec) -> dict[str, Any]:
    raw = deck.metadata.get(HEADER_FOOTER_KEY)
    settings = dict(DEFAULT_HEADER_FOOTER)
    if isinstance(raw, dict):
        settings.update({key: raw[key] for key in settings if key in raw})
    return settings


def set_header_footer(deck: DeckSpec, **values: Any) -> None:
    settings = header_footer_settings(deck)
    settings.update({key: values[key] for key in settings if key in values})
    deck.metadata[HEADER_FOOTER_KEY] = settings


def _date_text(settings: dict[str, Any], date_text: str | None = None) -> str:
    custom = str(settings.get("date_text") or "").strip()
    if custom:
        return custom
    if date_text is not None:
        return str(date_text)
    return datetime.now().strftime("%Y-%m-%d")


def slide_overlay_elements(
    deck: DeckSpec,
    slide_id: str,
    *,
    slide_index: int,
    slide_count: int,
    date_text: str | None = None,
) -> list[SlideElement]:
    settings = header_footer_settings(deck)
    overlays: list[SlideElement] = []
    font_size = 13
    color = deck.theme.muted or "#5E6A7D"
    if bool(settings.get("show_header")) and str(settings.get("header_text") or "").strip():
        overlays.append(
            SlideElement.text_box(
                f"__overlay-{slide_id}-header",
                str(settings.get("header_text") or ""),
                x=0.055,
                y=0.035,
                w=0.58,
                h=0.035,
                font_size=font_size,
                color=color,
            )
        )
    if bool(settings.get("show_footer")) and str(settings.get("footer_text") or "").strip():
        overlays.append(
            SlideElement.text_box(
                f"__overlay-{slide_id}-footer",
                str(settings.get("footer_text") or ""),
                x=0.055,
                y=0.925,
                w=0.45,
                h=0.035,
                font_size=font_size,
                color=color,
            )
        )
    if bool(settings.get("show_date")):
        overlays.append(
            SlideElement.text_box(
                f"__overlay-{slide_id}-date",
                _date_text(settings, date_text),
                x=0.42,
                y=0.925,
                w=0.24,
                h=0.035,
                font_size=font_size,
                color=color,
                align="center",
            )
        )
    if bool(settings.get("show_slide_number")):
        overlays.append(
            SlideElement.text_box(
                f"__overlay-{slide_id}-number",
                f"{max(1, int(slide_index))} / {max(1, int(slide_count))}",
                x=0.80,
                y=0.925,
                w=0.145,
                h=0.035,
                font_size=font_size,
                color=color,
                align="right",
            )
        )
    for element in overlays:
        element.locked = True
        element.z_index = 9000
        element.metadata["overlay"] = HEADER_FOOTER_KEY
    return overlays


__all__ = [
    "DEFAULT_HEADER_FOOTER",
    "HEADER_FOOTER_KEY",
    "header_footer_settings",
    "set_header_footer",
    "slide_overlay_elements",
]
