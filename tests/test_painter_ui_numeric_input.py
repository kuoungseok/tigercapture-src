from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_numeric_expression_supports_relative_and_absolute_arithmetic() -> None:
    from app.painter_ui_numeric_input import evaluate_painter_numeric_input

    evaluate = lambda text: evaluate_painter_numeric_input(text, origin=100.0)
    assert evaluate("+20") == 120.0
    assert evaluate("*1.5") == 150.0
    assert evaluate("/4") == 25.0
    assert evaluate("50%") == 50.0
    assert evaluate("25 + 5 * 2") == 35.0
    assert evaluate("-8") == -8.0


def test_numeric_expression_rejects_code_and_unsafe_operators() -> None:
    from app.painter_ui_numeric_input import evaluate_painter_numeric_input

    for expression in ("name", "__import__('os')", "2**8", "1//2", "1/0"):
        with pytest.raises(ValueError):
            evaluate_painter_numeric_input(expression, origin=100.0)


def test_drag_spin_boxes_interpret_expressions_with_prefix_and_suffix() -> None:
    app = _app()
    from PySide6.QtGui import QValidator

    from app.painter_ui_inspector import (
        PainterUIDragDoubleSpinBox,
        PainterUIDragSpinBox,
    )

    size = PainterUIDragDoubleSpinBox()
    size.setRange(0.0, 1000.0)
    size.setSuffix(" px")
    size.setValue(100.0)
    size._edit_origin_value = 100.0
    assert size.validate("*1.5 px", 4)[0] == QValidator.State.Acceptable
    size.lineEdit().setText("*1.5 px")
    size.interpretText()
    assert size.value() == 150.0

    count = PainterUIDragSpinBox()
    count.setRange(0, 1000)
    count.setValue(12)
    count._edit_origin_value = 12.0
    count.lineEdit().setText("+8")
    count.interpretText()
    assert count.value() == 20

    size.deleteLater()
    count.deleteLater()
    app.processEvents()


def test_reset_to_default_emits_the_normal_commit_signal() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIDragDoubleSpinBox

    spin = PainterUIDragDoubleSpinBox()
    spin.setRange(0.0, 1000.0)
    spin.setResetValue(64.0)
    spin.setValue(240.0)
    commits: list[float] = []
    spin.editingFinished.connect(lambda: commits.append(spin.value()))

    assert spin.resetToDefault() is True
    assert spin.value() == 64.0
    assert commits == [64.0]

    spin.deleteLater()
    app.processEvents()


def test_inspector_arithmetic_commit_uses_existing_undoable_geometry_path() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 700, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._create_painter_ui_object_from_rect(
        "rectangle",
        40.0,
        60.0,
        120.0,
        48.0,
    )
    dialog._refresh_painter_ui_overlay()
    width = dialog._paint_ui_inspector.geometry_controls["width"]
    width._edit_origin_value = 120.0
    width.lineEdit().setText("*2")
    width.interpretText()
    width.editingFinished.emit()

    row = dialog._painter_ui_document["objects"][0]
    assert row["width"] == 240.0
    assert dialog._undo_labels[-1] == "Edit UI object"
    dialog._undo()
    assert dialog._painter_ui_document["objects"][0]["width"] == 120.0

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
