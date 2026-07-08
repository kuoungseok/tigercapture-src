"""Font helpers for the PPT generator."""
from __future__ import annotations

from collections.abc import Iterable


DEFAULT_FONT_FAMILY = "Noto Sans KR"

RECOMMENDED_FONTS = [
    "Noto Sans KR",
    "Malgun Gothic",
    "Pretendard",
    "Segoe UI",
    "Arial",
    "Times New Roman",
    "Georgia",
    "Consolas",
]

_PIL_WINDOWS_FONT_FILES = {
    "malgun gothic": {
        (False, False): "malgun.ttf",
        (True, False): "malgunbd.ttf",
        (False, True): "malgun.ttf",
        (True, True): "malgunbd.ttf",
    },
    "noto sans kr": {
        (False, False): "malgun.ttf",
        (True, False): "malgunbd.ttf",
        (False, True): "malgun.ttf",
        (True, True): "malgunbd.ttf",
    },
    "pretendard": {
        (False, False): "malgun.ttf",
        (True, False): "malgunbd.ttf",
        (False, True): "malgun.ttf",
        (True, True): "malgunbd.ttf",
    },
    "segoe ui": {
        (False, False): "segoeui.ttf",
        (True, False): "segoeuib.ttf",
        (False, True): "segoeuii.ttf",
        (True, True): "segoeuiz.ttf",
    },
    "arial": {
        (False, False): "arial.ttf",
        (True, False): "arialbd.ttf",
        (False, True): "ariali.ttf",
        (True, True): "arialbi.ttf",
    },
    "times new roman": {
        (False, False): "times.ttf",
        (True, False): "timesbd.ttf",
        (False, True): "timesi.ttf",
        (True, True): "timesbi.ttf",
    },
    "georgia": {
        (False, False): "georgia.ttf",
        (True, False): "georgiab.ttf",
        (False, True): "georgiai.ttf",
        (True, True): "georgiaz.ttf",
    },
    "consolas": {
        (False, False): "consola.ttf",
        (True, False): "consolab.ttf",
        (False, True): "consolai.ttf",
        (True, True): "consolaz.ttf",
    },
}


def normalize_font_family(value: str | None, *, default: str = DEFAULT_FONT_FAMILY) -> str:
    family = str(value or "").strip()
    return family or default


def recommended_font_families(installed: Iterable[str] | None = None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    installed_rows = [normalize_font_family(row) for row in installed or [] if str(row or "").strip()]
    installed_lookup = {row.lower(): row for row in installed_rows}

    for family in RECOMMENDED_FONTS:
        resolved = installed_lookup.get(family.lower(), family)
        key = resolved.lower()
        if key not in seen:
            ordered.append(resolved)
            seen.add(key)

    for family in sorted(installed_rows, key=str.lower):
        key = family.lower()
        if key not in seen:
            ordered.append(family)
            seen.add(key)
    return ordered


def pil_font_candidates(family: str | None, *, bold: bool = False, italic: bool = False) -> list[str]:
    key = normalize_font_family(family).lower()
    file_name = _PIL_WINDOWS_FONT_FILES.get(key, {}).get((bool(bold), bool(italic)))
    candidates: list[str] = []
    if file_name:
        candidates.append(f"C:/Windows/Fonts/{file_name}")
    for fallback in ("malgunbd.ttf" if bold else "malgun.ttf", "arialbd.ttf" if bold else "arial.ttf"):
        path = f"C:/Windows/Fonts/{fallback}"
        if path not in candidates:
            candidates.append(path)
    return candidates


__all__ = [
    "DEFAULT_FONT_FAMILY",
    "RECOMMENDED_FONTS",
    "normalize_font_family",
    "pil_font_candidates",
    "recommended_font_families",
]
