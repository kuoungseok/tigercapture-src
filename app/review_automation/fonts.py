from __future__ import annotations

from pathlib import Path
from typing import Any


REVIEW_FONT_CSS = (
    '"Cascadia Mono", "Consolas", "IBM Plex Mono", "Roboto Mono", '
    '"Pretendard", "Pretendard Variable", '
    '"Noto Sans CJK KR", "Noto Sans KR", '
    '"Malgun Gothic", "Apple SD Gothic Neo", '
    '"Noto Sans CJK JP", "Noto Sans JP", '
    '"Microsoft YaHei UI", "Segoe UI Variable", "Segoe UI", '
    '"Arial", sans-serif'
)
REVIEW_PPT_FONT = "Cascadia Mono"
REVIEW_KO_PPT_FONT = "Malgun Gothic"

PIL_REGULAR_CANDIDATES = (
    Path("C:/Windows/Fonts/CascadiaMono.ttf"),
    Path("C:/Windows/Fonts/CascadiaCode.ttf"),
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("C:/Windows/Fonts/NotoSansCJK-Regular.ttc"),
    Path("C:/Windows/Fonts/NotoSansKR-Regular.otf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
PIL_KO_REGULAR_CANDIDATES = (
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("C:/Windows/Fonts/NotoSansCJK-Regular.ttc"),
    Path("C:/Windows/Fonts/NotoSansKR-Regular.otf"),
    Path("C:/Windows/Fonts/CascadiaMono.ttf"),
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
PIL_BOLD_CANDIDATES = (
    Path("C:/Windows/Fonts/CascadiaCode.ttf"),
    Path("C:/Windows/Fonts/consolab.ttf"),
    Path("C:/Windows/Fonts/malgunbd.ttf"),
    Path("C:/Windows/Fonts/NotoSansCJK-Bold.ttc"),
    Path("C:/Windows/Fonts/NotoSansKR-Bold.otf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
PIL_KO_BOLD_CANDIDATES = (
    Path("C:/Windows/Fonts/malgunbd.ttf"),
    Path("C:/Windows/Fonts/NotoSansCJK-Bold.ttc"),
    Path("C:/Windows/Fonts/NotoSansKR-Bold.otf"),
    Path("C:/Windows/Fonts/CascadiaCode.ttf"),
    Path("C:/Windows/Fonts/consolab.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)


def is_korean_locale(locale: str | None) -> bool:
    return str(locale or "").strip().lower().replace("_", "-").startswith("ko")


def review_ppt_font(locale: str | None = None) -> str:
    return REVIEW_KO_PPT_FONT if is_korean_locale(locale) else REVIEW_PPT_FONT


def load_pil_font(size: int, *, bold: bool = False, locale: str | None = None) -> Any:
    from PIL import ImageFont

    if is_korean_locale(locale):
        candidates = PIL_KO_BOLD_CANDIDATES if bold else PIL_KO_REGULAR_CANDIDATES
    else:
        candidates = PIL_BOLD_CANDIDATES if bold else PIL_REGULAR_CANDIDATES
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()
