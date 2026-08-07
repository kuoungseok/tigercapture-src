"""Contract for switching the runtime language."""
from __future__ import annotations

import importlib


def _fresh_i18n():
    """A module instance that has not resolved a language yet.

    ``initialize()`` latches on first use, so the ordering bug this pins only
    reproduces on a module that nothing has translated through yet.
    """
    import app.i18n as i18n

    return importlib.reload(i18n)


def test_an_explicit_language_survives_the_first_translation() -> None:
    from app.locales import en, ko

    key = "anim.cascade"
    assert ko.TRANSLATIONS[key] != en.TRANSLATIONS[key]

    i18n = _fresh_i18n()
    try:
        i18n.set_language("ko")
        # The first tr() used to run initialize(), which overwrote the choice
        # with the saved or detected language.
        assert i18n.tr(key) == ko.TRANSLATIONS[key]
        assert i18n.current_language() == "ko"
    finally:
        importlib.reload(i18n)


def test_an_explicit_language_still_wins_after_initialize() -> None:
    i18n = _fresh_i18n()
    try:
        i18n.initialize()
        i18n.set_language("ja")
        assert i18n.current_language() == "ja"
    finally:
        importlib.reload(i18n)


def test_an_unsupported_code_changes_nothing() -> None:
    i18n = _fresh_i18n()
    try:
        i18n.set_language("ko")
        i18n.set_language("kl")
        assert i18n.current_language() == "ko"
    finally:
        importlib.reload(i18n)
