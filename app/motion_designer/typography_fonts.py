"""Font fallback, variable-axis application, and typography preflight."""
from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo


DEFAULT_FONT_FALLBACKS = ("Noto Sans KR", "Malgun Gothic", "Segoe UI", "Arial")


def resolve_font_family(requested: str, fallbacks=DEFAULT_FONT_FALLBACKS) -> tuple[str, bool]:
    families = {name.casefold(): name for name in QFontDatabase.families()}
    key = str(requested or "").strip().casefold()
    if key and key in families:
        return families[key], False
    for candidate in fallbacks:
        if candidate.casefold() in families:
            return families[candidate.casefold()], bool(key)
    resolved = QFontInfo(QFont(str(requested or "Sans Serif"))).family()
    return resolved or "Sans Serif", bool(key)


def apply_variable_axes(font: QFont, axes: Mapping[str, object] | None) -> list[str]:
    invalid: list[str] = []
    for name, raw in (axes or {}).items():
        axis_name = str(name)
        if len(axis_name) != 4:
            invalid.append(axis_name)
            continue
        tag = QFont.Tag.fromString(axis_name)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            invalid.append(str(name))
            continue
        if not tag.isValid():
            invalid.append(str(name))
            continue
        font.setVariableAxis(tag, value)
    return invalid


def typography_preflight(params: Mapping[str, object]) -> dict[str, object]:
    requested = str(params.get("font_family") or "Noto Sans KR")
    resolved, fallback_used = resolve_font_family(requested)
    font = QFont(resolved)
    axes = params.get("font_axes") if isinstance(params.get("font_axes"), Mapping) else {}
    invalid_axes = apply_variable_axes(font, axes)
    return {
        "ok": not invalid_axes,
        "requested_family": requested,
        "resolved_family": resolved,
        "fallback_used": fallback_used,
        "missing_font": fallback_used,
        "variable_axes": dict(axes),
        "invalid_axes": invalid_axes,
    }
