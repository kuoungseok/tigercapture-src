"""Application-wide UI font fallback helpers."""
from __future__ import annotations

import sys
from collections.abc import Iterable
from functools import lru_cache
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

BUNDLED_UI_FONT_FILES = (
    "InterVariable.ttf",
    "InterVariable-Italic.ttf",
)

DESIGN_FONT_ALIASES = {
    "inter": ("Inter", "Inter Variable", "Inter Variable Text"),
}


def _resource_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    roots.extend((Path(__file__).resolve().parents[1], Path.cwd()))
    return tuple(dict.fromkeys(path.resolve() for path in roots))


def _bundled_ui_font_paths() -> tuple[str, ...]:
    paths: list[str] = []
    for root in _resource_roots():
        font_root = root / "resources" / "fonts"
        for name in BUNDLED_UI_FONT_FILES:
            candidate = font_root / name
            if candidate.is_file():
                resolved = str(candidate.resolve())
                if resolved not in paths:
                    paths.append(resolved)
    return tuple(paths)


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


def resolve_design_font_family(
    requested_family: str,
    available_families: Iterable[str],
) -> str:
    """Resolve stable document family names to bundled Qt family names."""
    requested = str(requested_family or "").strip()
    available = {str(name).casefold(): str(name) for name in available_families}
    exact = available.get(requested.casefold())
    if exact:
        return exact
    for candidate in DESIGN_FONT_ALIASES.get(requested.casefold(), ()):
        resolved = available.get(candidate.casefold())
        if resolved:
            return resolved
    return requested


@lru_cache(maxsize=64)
def registered_design_font_family(requested_family: str) -> str:
    """Resolve a document font against the current Qt font database."""
    from PySide6.QtGui import QFontDatabase

    return resolve_design_font_family(
        requested_family,
        QFontDatabase.families(),
    )


def load_application_ui_fonts() -> tuple[str, ...]:
    """Register bundled design fonts and OS CJK fallbacks with Qt.

    PySide's offscreen platform can report no system fonts at all on Windows,
    which makes screenshots render translated UI text as tofu boxes. Loading
    known Windows font files as application fonts keeps QA captures readable.
    Inter is bundled so Figma text uses the same metrics on every machine.
    """
    from PySide6.QtGui import QFontDatabase

    loaded_families: list[str] = []
    for path in (*_bundled_ui_font_paths(), *_existing_system_font_paths()):
        if path in _APPLICATION_FONT_PATHS:
            continue
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id < 0:
            continue
        _APPLICATION_FONT_IDS.append(font_id)
        _APPLICATION_FONT_PATHS.add(path)
        loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))
    if loaded_families:
        registered_design_font_family.cache_clear()
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
