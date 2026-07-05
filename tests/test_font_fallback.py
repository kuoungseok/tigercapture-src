import os
from pathlib import Path

import pytest

from app.font_fallback import PREFERRED_UI_FONTS, apply_ui_font, choose_ui_font


def test_choose_ui_font_prefers_korean_safe_family():
    assert choose_ui_font(["Segoe UI", "Noto Sans KR"]) == "Noto Sans KR"


def test_choose_ui_font_falls_back_to_segoe():
    assert choose_ui_font([]) == "Segoe UI"


def test_choose_ui_font_prefers_malgun_over_latin_only_family():
    assert choose_ui_font(["Segoe UI", "Malgun Gothic"]) == "Malgun Gothic"


def test_apply_ui_font_registers_windows_cjk_font_for_offscreen_capture():
    if not Path("C:/Windows/Fonts/malgun.ttf").exists():
        pytest.skip("Windows Malgun Gothic font is not available")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    family = apply_ui_font(app)

    assert family in PREFERRED_UI_FONTS
    assert "Malgun Gothic" in QFontDatabase.families()
