from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_combo_selection_uses_semantic_data_not_visual_row_order() -> None:
    _app()
    from PySide6.QtWidgets import QComboBox

    from app.painter_combo_selection import select_combo_data

    combo = QComboBox()
    combo.addItem("Unrelated first row", "other")
    combo.addItem("Declared fallback", "normal")
    combo.addItem("Requested", "multiply")

    assert select_combo_data(combo, "multiply", fallback_data="normal") is True
    assert combo.currentData() == "multiply"
    assert select_combo_data(combo, "missing", fallback_data="normal") is False
    assert combo.currentData() == "normal"


def test_combo_selection_rejects_a_missing_declared_fallback() -> None:
    _app()
    from PySide6.QtWidgets import QComboBox

    from app.painter_combo_selection import select_combo_data

    combo = QComboBox()
    combo.addItem("Unrelated first row", "other")

    with pytest.raises(ValueError, match="fallback data is missing"):
        select_combo_data(combo, "missing", fallback_data="normal")
    assert combo.currentData() == "other"
