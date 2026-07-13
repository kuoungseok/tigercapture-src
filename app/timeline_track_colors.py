from __future__ import annotations

from typing import Any

from PySide6.QtGui import QColor


_CATALOG_TRACK_PALETTES = (
    ("#5A432F", "#75583A", "#D99B5D"),
    ("#38495D", "#4B627A", "#89B4D6"),
    ("#41533F", "#536C52", "#9ACB8C"),
    ("#51405D", "#665179", "#BE98D8"),
    ("#564B35", "#6D6042", "#D5B36A"),
)
_PERFORMANCE_SOURCE_PALETTE = ("#303440", "#3C4251", "#868CA0")


def catalog_track_palette(track: Any) -> tuple[QColor, QColor, QColor]:
    try:
        idx = max(0, int(getattr(track, "id", 0) or 0) - 1) % len(_CATALOG_TRACK_PALETTES)
    except Exception:
        idx = 0
    return tuple(QColor(color) for color in _CATALOG_TRACK_PALETTES[idx])


def is_performance_source_track(track: Any) -> bool:
    try:
        from app.vtuber.performance_source import is_performance_source_track as _is_perf

        return bool(_is_perf(track))
    except Exception:
        return bool(
            getattr(track, "vtuber_performance_source", False)
            or getattr(track, "performance_source", False)
            or str(getattr(track, "track_type", "") or "").casefold() == "vtuber_performance_source"
        )


def track_palette_for_track(track: Any) -> tuple[QColor, QColor, QColor]:
    if is_performance_source_track(track):
        return tuple(QColor(color) for color in _PERFORMANCE_SOURCE_PALETTE)
    return catalog_track_palette(track)


def track_accent_color(track: Any) -> QColor:
    return track_palette_for_track(track)[2]


def track_context_label(track: Any) -> str:
    try:
        idx = max(1, int(getattr(track, "id", 0) or 0))
    except Exception:
        idx = 0
    prefix = "P" if is_performance_source_track(track) else "V"
    return f"{prefix}{idx}" if idx > 0 else prefix


__all__ = [
    "catalog_track_palette",
    "is_performance_source_track",
    "track_accent_color",
    "track_context_label",
    "track_palette_for_track",
]
