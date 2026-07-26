from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _text_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844, name="Phone")
    return add_ui_object(
        document,
        kind="text",
        name="Headline",
        x=24,
        y=48,
        width=280,
        height=72,
        style={"fill": "#F5F7FA", "font_size": 18},
        content={"text": "Tiger Studio"},
    )


def test_inspector_emits_visual_and_typography_properties() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    document, row = _text_document()
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[tuple[str, dict]] = []
    inspector.properties_changed.connect(
        lambda object_id, changes: emitted.append((object_id, changes))
    )

    inspector.fill_edit.setText("#102030")
    inspector.stroke_edit.setText("#D9E1EA")
    inspector.stroke_width_spin.setValue(2.5)
    inspector.radius_spin.setValue(12)
    inspector.shadow_color_edit.setText("#00000055")
    inspector.shadow_y_spin.setValue(6)
    inspector.shadow_blur_spin.setValue(18)
    inspector.text_edit.setText("Design system")
    inspector.font_size_spin.setValue(28)
    inspector.font_weight_combo.setCurrentIndex(
        inspector.font_weight_combo.findData(600)
    )
    inspector.text_align_combo.setCurrentIndex(
        inspector.text_align_combo.findData("center")
    )
    inspector.line_height_spin.setValue(1.45)
    inspector._emit_properties()

    assert emitted
    object_id, changes = emitted[-1]
    assert object_id == row["id"]
    assert changes["content"]["text"] == "Design system"
    assert changes["style"] == {
        "fill": "#102030",
        "font_size": 28.0,
        "stroke": "#D9E1EA",
        "stroke_width": 2.5,
        "radius": 12.0,
        "shadow": {
            "x": 0.0,
            "y": 6.0,
            "blur": 18.0,
            "spread": 0.0,
            "color": "#00000055",
        },
        "font_weight": 600,
        "text_align": "center",
        "line_height": 1.45,
    }
    inspector.deleteLater()
    app.processEvents()


def test_inspector_disables_text_controls_for_non_text_and_empty_selection() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(390, 844, name="Phone")
    document, _row = add_ui_object(document, kind="rectangle", name="Panel")
    inspector = PainterUIInspector()
    inspector.set_document(document)
    assert not inspector.text_edit.isEnabled()
    assert not inspector.font_size_spin.isEnabled()

    document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = []
    inspector.set_document(document)
    assert not inspector.stroke_edit.isEnabled()
    assert not inspector.text_edit.isEnabled()
    assert inspector.text_edit.text() == ""
    inspector.deleteLater()
    app.processEvents()


def test_inspector_payload_round_trips_through_document_update() -> None:
    app = _app()
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_inspector import PainterUIInspector

    document, row = _text_document()
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[dict] = []
    inspector.properties_changed.connect(
        lambda _object_id, changes: emitted.append(changes)
    )
    inspector.stroke_edit.setText("#8899AA")
    inspector.stroke_width_spin.setValue(1.5)
    inspector.text_edit.setText("Round trip")
    inspector.font_weight_combo.setCurrentIndex(
        inspector.font_weight_combo.findData(700)
    )
    inspector._emit_properties()

    updated, updated_row = update_ui_object(document, row["id"], emitted[-1])
    restored = next(item for item in updated["objects"] if item["id"] == row["id"])
    assert updated_row == restored
    assert restored["content"]["text"] == "Round trip"
    assert restored["style"]["stroke"] == "#8899AA"
    assert restored["style"]["stroke_width"] == 1.5
    assert restored["style"]["font_weight"] == 700
    inspector.deleteLater()
    app.processEvents()


def test_inspector_emits_pivot_constraints_and_size_policy() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(390, 844, name="Phone")
    document, row = add_ui_object(
        document,
        kind="rectangle",
        name="Footer",
        x=24,
        y=720,
        width=342,
        height=72,
    )
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[dict] = []
    inspector.properties_changed.connect(
        lambda _object_id, changes: emitted.append(changes)
    )

    inspector.pivot_x_spin.setValue(0.25)
    inspector.pivot_y_spin.setValue(0.75)
    inspector.horizontal_constraint_combo.setCurrentIndex(
        inspector.horizontal_constraint_combo.findData("right")
    )
    inspector.vertical_constraint_combo.setCurrentIndex(
        inspector.vertical_constraint_combo.findData("bottom")
    )
    inspector.size_limit_controls["min_width"].setValue(240)
    inspector.size_limit_controls["min_height"].setValue(48)
    inspector.size_limit_controls["preferred_width"].setValue(342)
    inspector.size_limit_controls["preferred_height"].setValue(72)
    inspector.size_limit_controls["max_width"].setValue(480)
    inspector.size_limit_controls["max_height"].setValue(96)
    inspector.aspect_lock_check.setChecked(True)
    inspector._emit_properties()

    constraints = emitted[-1]["constraints"]
    assert constraints["horizontal"] == "right"
    assert constraints["vertical"] == "bottom"
    assert constraints["pivot_x"] == 0.25
    assert constraints["pivot_y"] == 0.75
    assert constraints["min_width"] == 240.0
    assert constraints["max_height"] == 96.0
    assert constraints["lock_aspect"] is True
    assert constraints["aspect_ratio"] == 342 / 72
    assert constraints["right"] == 24.0
    assert constraints["bottom"] == 52.0
    assert constraints["reference_parent_width"] == 390.0
    assert constraints["reference_parent_height"] == 844.0
    assert row["id"] == document["selection"]["object_id"]
    inspector.deleteLater()
    app.processEvents()


def test_inspector_geometry_obeys_locked_aspect_and_size_limits() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(800, 600)
    document, row = add_ui_object(
        document,
        kind="rectangle",
        width=200,
        height=100,
    )
    row = document["objects"][0]
    row["constraints"] = {
        "lock_aspect": True,
        "aspect_ratio": 2.0,
        "min_width": 120.0,
        "min_height": 60.0,
        "max_width": 240.0,
        "max_height": 120.0,
    }
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[dict] = []
    inspector.geometry_changed.connect(
        lambda _object_id, changes: emitted.append(changes)
    )
    inspector.geometry_controls["width"].setValue(400)
    inspector.geometry_controls["height"].setValue(300)
    inspector._emit_geometry()

    assert emitted[-1]["width"] == 240.0
    assert emitted[-1]["height"] == 120.0
    inspector.deleteLater()
    app.processEvents()


def test_inspector_style_changes_use_dialog_undo_path() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._add_default_painter_ui_object("text")
    row = dialog._painter_ui_document["objects"][-1]
    original_style = dict(row["style"])
    original_content = dict(row["content"])
    dialog._update_painter_ui_object_changes(
        row["id"],
        {
            "style": {
                **original_style,
                "stroke": "#AABBCC",
                "stroke_width": 2.0,
                "font_weight": 700,
            },
            "content": {"text": "Undo me"},
        },
    )
    changed = dialog._painter_ui_document["objects"][-1]
    assert changed["style"]["stroke_width"] == 2.0
    assert changed["content"]["text"] == "Undo me"

    dialog._undo()
    restored = dialog._painter_ui_document["objects"][-1]
    assert restored["style"] == original_style
    assert restored["content"] == original_content
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_constraint_geometry_changes_use_dialog_undo_path() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._add_default_painter_ui_object("rectangle")
    row = dialog._painter_ui_document["objects"][-1]
    original_x = float(row["x"])
    original_constraints = dict(row["constraints"])
    dialog._update_painter_ui_object_changes(
        row["id"],
        {
            "x": original_x + 40.0,
            "constraints": {
                **original_constraints,
                "horizontal": "right",
                "pivot_x": 0.25,
            },
        },
    )
    changed = dialog._painter_ui_document["objects"][-1]
    assert changed["x"] == original_x + 40.0
    assert changed["constraints"]["horizontal"] == "right"
    assert changed["constraints"]["pivot_x"] == 0.25
    assert "right" in changed["constraints"]

    dialog._undo()
    restored = dialog._painter_ui_document["objects"][-1]
    assert restored["x"] == original_x
    assert restored["constraints"] == original_constraints
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
