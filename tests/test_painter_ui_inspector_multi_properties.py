from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _multi_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(900, 700, name="Desktop")
    document, first = add_ui_object(
        document,
        kind="rectangle",
        name="Primary",
        style={
            "fill": "#335577",
            "stroke": "#DDEEFF",
            "stroke_width": 1.0,
            "radius": 8.0,
        },
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        name="Secondary",
        style={
            "fill": "#335577",
            "stroke": "#223344",
            "stroke_width": 3.0,
            "radius": 18.0,
        },
    )
    for row in document["objects"]:
        if row["id"] == first["id"]:
            row["opacity"] = 1.0
            row["visible"] = True
        elif row["id"] == second["id"]:
            row["opacity"] = 0.6
            row["visible"] = False
    document["selection"] = {
        "object_id": first["id"],
        "object_ids": [first["id"], second["id"]],
    }
    return document, first, second


def test_multi_inspector_shows_common_and_mixed_values() -> None:
    app = _app()
    from PySide6.QtCore import Qt

    from app.painter_ui_inspector import PainterUIInspector

    document, _first, _second = _multi_document()
    inspector = PainterUIInspector()
    inspector.set_document(document)

    assert inspector.design_context() == "multi"
    assert inspector.design_group_visible("multi_properties")
    assert inspector.design_group_visible("arrange")
    assert inspector.multi_fill_edit.text() == "#335577"
    assert inspector.multi_fill_edit.placeholderText() == "#RRGGBB"
    assert inspector.multi_opacity_spin.value() == -1
    assert inspector.multi_opacity_spin.specialValueText() == "—"
    assert inspector.multi_stroke_edit.text() == ""
    assert inspector.multi_stroke_edit.placeholderText() == "—"
    assert inspector.multi_radius_spin.value() == -1.0
    assert (
        inspector.multi_visible_check.checkState()
        == Qt.CheckState.PartiallyChecked
    )
    assert inspector.multi_locked_check.checkState() == Qt.CheckState.Unchecked

    inspector.deleteLater()
    app.processEvents()


def test_multi_inspector_emits_only_edited_property_for_every_object() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    document, first, second = _multi_document()
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[dict] = []
    inspector.batch_properties_changed.connect(emitted.append)

    inspector.multi_fill_edit.setText("#9AA8B8")
    inspector._mark_multi_dirty("fill")
    inspector._emit_multi_property("fill")

    assert len(emitted) == 1
    changes = emitted[0]
    assert set(changes) == {first["id"], second["id"]}
    assert changes[first["id"]]["style"]["fill"] == "#9AA8B8"
    assert changes[second["id"]]["style"]["fill"] == "#9AA8B8"
    assert changes[first["id"]]["style"]["radius"] == 8.0
    assert changes[second["id"]]["style"]["radius"] == 18.0
    assert changes[first["id"]]["style"]["stroke"] == "#DDEEFF"
    assert changes[second["id"]]["style"]["stroke"] == "#223344"
    assert set(changes[first["id"]]) == {"style"}
    assert set(changes[second["id"]]) == {"style"}

    inspector.deleteLater()
    app.processEvents()


def test_multi_inspector_ignores_unedited_mixed_blank() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    document, _first, _second = _multi_document()
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[dict] = []
    inspector.batch_properties_changed.connect(emitted.append)

    inspector._emit_multi_property("stroke")

    assert emitted == []
    inspector.deleteLater()
    app.processEvents()


def test_multi_inspector_batch_edit_is_one_undoable_document_change() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, first, second = _multi_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 700, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    inspector = dialog._paint_ui_inspector

    inspector.multi_opacity_spin.setMinimum(0)
    inspector.multi_opacity_spin.setValue(72)
    inspector._emit_multi_property("opacity")

    rows = {
        row["id"]: row
        for row in dialog._painter_ui_document["objects"]
    }
    assert rows[first["id"]]["opacity"] == 0.72
    assert rows[second["id"]]["opacity"] == 0.72
    assert dialog._undo_labels[-1] == "Edit UI objects"
    dialog._undo()
    restored = {
        row["id"]: row
        for row in dialog._painter_ui_document["objects"]
    }
    assert restored[first["id"]]["opacity"] == 1.0
    assert restored[second["id"]]["opacity"] == 0.6

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
