"""Application-wide UI font fallback helpers."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


_APPLICATION_FONT_IDS: list[int] = []
_APPLICATION_FONT_PATHS: set[str] = set()


PREFERRED_UI_FONTS = (
    "Pretendard Variable",
    "Pretendard",
    "Noto Sans CJK KR",
    "Noto Sans KR",
    "Malgun Gothic",
    "Apple SD Gothic Neo",
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "Microsoft YaHei UI",
    "Segoe UI Variable",
    "Segoe UI",
    "Arial",
    "Tahoma",
)

WINDOWS_UI_FONT_FILES = (
    "malgun.ttf",
    "malgunbd.ttf",
    "malgunsl.ttf",
    "msgothic.ttc",
    "msyh.ttc",
    "msyhbd.ttc",
    "msyhl.ttc",
)


def _existing_system_font_paths() -> tuple[str, ...]:
    candidates: list[Path] = []
    windows_fonts = Path("C:/Windows/Fonts")
    if windows_fonts.exists():
        candidates.extend(windows_fonts / name for name in WINDOWS_UI_FONT_FILES)
    return tuple(str(path) for path in candidates if path.exists())


def choose_ui_font(available_families: Iterable[str]) -> str:
    available = {str(name).casefold(): str(name) for name in available_families}
    for family in PREFERRED_UI_FONTS:
        hit = available.get(family.casefold())
        if hit:
            return hit
    return "Segoe UI"


def load_application_ui_fonts() -> tuple[str, ...]:
    """Register OS CJK UI fonts for Qt environments with an empty font DB.

    PySide's offscreen platform can report no system fonts at all on Windows,
    which makes screenshots render translated UI text as tofu boxes. Loading
    known Windows font files as application fonts keeps QA captures readable.
    """
    from PySide6.QtGui import QFontDatabase

    loaded_families: list[str] = []
    for path in _existing_system_font_paths():
        if path in _APPLICATION_FONT_PATHS:
            continue
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id < 0:
            continue
        _APPLICATION_FONT_IDS.append(font_id)
        _APPLICATION_FONT_PATHS.add(path)
        loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return tuple(dict.fromkeys(loaded_families))


def apply_ui_font(app=None) -> str:
    """Set a stable default UI font and return the selected family."""
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    app = app or QApplication.instance()
    if app is None:
        return ""
    load_application_ui_fonts()
    family = choose_ui_font(QFontDatabase.families())
    current = app.font()
    font = QFont(family)
    size = current.pointSizeF()
    if size > 0:
        font.setPointSizeF(size)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    return family
