from __future__ import annotations

from typing import Any

from PySide6.QtCore import QLocale, QSettings


SUPPORTED_LANGUAGES: dict[str, str] = {
    "ko": "한국어",
    "en": "English",
    "ja": "日本語",
    "de": "Deutsch",
}
DEFAULT_LANGUAGE = "en"

_SETTINGS_ORG = "GifCam"
_SETTINGS_APP = "GifCam"
_LANGUAGE_KEY = "language"

_translations: dict[str, dict[str, str]] = {}
_current_lang: str = DEFAULT_LANGUAGE
_initialized: bool = False


def _load_translations() -> None:
    global _translations
    from app.locales import de, en, ja, ko

    _translations = {
        "ko": ko.TRANSLATIONS,
        "en": en.TRANSLATIONS,
        "ja": ja.TRANSLATIONS,
        "de": de.TRANSLATIONS,
    }


def detect_system_language() -> str:
    """Detect Windows/OS language via ``QLocale.system()``.

    Returns a supported language code, falling back to DEFAULT_LANGUAGE.
    """
    name = QLocale.system().name()  # e.g. "ko_KR", "en_US", "ja_JP"
    code = name.split("_")[0].lower()
    if code in SUPPORTED_LANGUAGES:
        return code
    return DEFAULT_LANGUAGE


def saved_language() -> str | None:
    settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    value = settings.value(_LANGUAGE_KEY, None)
    if isinstance(value, str) and value in SUPPORTED_LANGUAGES:
        return value
    return None


def save_language(code: str) -> None:
    if code not in SUPPORTED_LANGUAGES:
        return
    settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    settings.setValue(_LANGUAGE_KEY, code)
    settings.sync()
    import sys

    print(f"[i18n] saved language -> {code}", file=sys.stderr, flush=True)


def initialize() -> str:
    """Load translation tables and set the active language from saved settings
    or system locale. Returns the resolved language code.
    """
    global _current_lang, _initialized
    if not _translations:
        _load_translations()
    saved = saved_language()
    detected = detect_system_language()
    chosen = saved or detected
    if chosen not in SUPPORTED_LANGUAGES:
        chosen = DEFAULT_LANGUAGE
    _current_lang = chosen
    _initialized = True
    import sys

    print(
        f"[i18n] saved={saved} detected={detected} active={chosen}",
        file=sys.stderr,
        flush=True,
    )
    return _current_lang


def set_language(code: str) -> None:
    """Switch runtime language (does not persist; use ``save_language`` too)."""
    global _current_lang
    if code in SUPPORTED_LANGUAGES:
        _current_lang = code


def current_language() -> str:
    if not _initialized:
        initialize()
    return _current_lang


def tr(key: str, **kwargs: Any) -> str:
    """Translate a key. Falls back to English, then the key itself.

    Supports ``{placeholder}`` substitutions via ``kwargs``.
    """
    if not _initialized:
        initialize()
    lang_table = _translations.get(_current_lang, {})
    text = lang_table.get(key)
    if text is None:
        text = _translations.get(DEFAULT_LANGUAGE, {}).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text
