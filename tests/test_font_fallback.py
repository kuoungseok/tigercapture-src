import os
from pathlib import Path

import pytest

from app.font_fallback import (
    PREFERRED_UI_FONTS,
    apply_ui_font,
    choose_ui_font,
    resolve_design_font_family,
)


def test_choose_ui_font_prefers_korean_safe_family():
    assert choose_ui_font(["Segoe UI", "Noto Sans KR"]) == "Noto Sans KR"


def test_choose_ui_font_falls_back_to_segoe():
    assert choose_ui_font([]) == "Segoe UI"


def test_choose_ui_font_prefers_malgun_over_latin_only_family():
    assert choose_ui_font(["Segoe UI", "Malgun Gothic"]) == "Malgun Gothic"


def test_inter_document_family_resolves_to_bundled_variable_family():
    assert (
        resolve_design_font_family(
            "Inter",
            ["Tahoma", "Inter Variable", "Malgun Gothic"],
        )
        == "Inter Variable"
    )


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


def test_apply_ui_font_registers_inter_for_figma_rendering():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QFontInfo
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_style_renderer import ui_font

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    font = ui_font(
        app.font(),
        {"font_family": "Inter", "font_size": 16, "font_weight": 500},
    )

    assert font.family() == "Inter Variable"
    assert QFontInfo(font).family() == "Inter Variable"
    assert QFontInfo(font).exactMatch() is True


def test_pyinstaller_specs_bundle_fonts_and_license():
    windows_spec = Path("TigerCapture.spec").read_text(encoding="utf-8")
    mac_spec = Path("mac/TigerCapture-mac.spec").read_text(encoding="utf-8")

    for contents in (windows_spec, mac_spec):
        assert "resources/fonts" in contents
        assert "*.ttf" in contents
        assert "*.txt" in contents
