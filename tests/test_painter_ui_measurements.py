from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_objects,
    )

    document = create_ui_document(800, 600)
    document, left = add_ui_object(
        document,
        kind="rectangle",
        name="Left",
        x=40,
        y=120,
        width=60,
        height=80,
    )
    document, selected = add_ui_object(
        document,
        kind="rectangle",
        name="Selected",
        x=140,
        y=100,
        width=120,
        height=120,
    )
    document, right = add_ui_object(
        document,
        kind="rectangle",
        name="Right",
        x=300,
        y=120,
        width=80,
        height=80,
    )
    document = select_ui_objects(document, [selected["id"]])
    return document, left, selected, right


def test_measurements_choose_nearest_objects_and_artboard_edges() -> None:
    from app.painter_ui_measurements import (
        inspect_ui_selection_measurements,
    )

    document, left, selected, right = _document()
    report = inspect_ui_selection_measurements(document)

    assert report["schema"] == "tigerstudio.painter.ui.measurements.v1"
    assert report["eligible"] is True
    assert report["object_ids"] == [selected["id"]]
    distances = {row["side"]: row for row in report["distances"]}
    assert distances["left"]["value"] == 40.0
    assert distances["left"]["target_object_id"] == left["id"]
    assert distances["right"]["value"] == 40.0
    assert distances["right"]["target_object_id"] == right["id"]
    assert distances["top"]["value"] == 100.0
    assert distances["top"]["target_kind"] == "artboard"
    assert distances["bottom"]["value"] == 380.0


def test_measurements_are_read_only_and_report_empty_selection() -> None:
    from app.painter_ui_measurements import (
        inspect_ui_selection_measurements,
    )

    document, _left, _selected, _right = _document()
    before = copy.deepcopy(document)
    report = inspect_ui_selection_measurements(document, object_ids=[])

    assert report["eligible"] is False
    assert report["reason"] == "no_selection"
    assert document == before


def test_workspace_alt_only_toggles_transient_measurements() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, _left, _selected, _right = _document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    overlay.show()
    overlay.setFocus()
    app.processEvents()

    QTest.keyPress(overlay, Qt.Key.Key_Alt)
    assert overlay._measurements_visible is True
    assert overlay.measurement_report()["eligible"] is True
    QTest.keyRelease(overlay, Qt.Key.Key_Alt)
    assert overlay._measurements_visible is False
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_measurement_action_matches_ui_report_without_mutating() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, _left, selected, _right = _document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    before = copy.deepcopy(dialog._painter_ui_document)
    registry = ActionRegistry(owner=dialog)

    result = registry.execute(
        "paint.ui.dev.measurement.inspect",
        {"object_ids": [selected["id"]]},
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["eligible"] is True
    assert dialog._painter_ui_document == before
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
