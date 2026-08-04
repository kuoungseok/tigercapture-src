from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_auto_layout_normalizes_aliases_and_preserves_positioning() -> None:
    from app.painter_ui_auto_layout import normalize_ui_auto_layout

    layout = normalize_ui_auto_layout(
        {
            "direction": "row",
            "padding": [12, 8],
            "gap": "14",
            "justify": "space_between",
            "align": "center",
            "position": "absolute",
        }
    )
    assert layout == {
        "mode": "horizontal",
        "padding": {"left": 12.0, "top": 8.0, "right": 12.0, "bottom": 8.0},
        "gap": 14.0,
        "cross_gap": 14.0,
        "main_alignment": "space_between",
        "cross_alignment": "center",
        "positioning": "absolute",
        "wrap": False,
        "width_sizing": "fixed",
        "height_sizing": "fixed",
        "grid_columns": 2,
        "grid_column_span": 1,
        "grid_row_span": 1,
        "cell_horizontal_alignment": "stretch",
        "cell_vertical_alignment": "stretch",
    }


def test_horizontal_auto_layout_applies_padding_gap_and_alignment() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, parent = add_ui_object(
        document,
        kind="frame",
        x=100,
        y=50,
        width=400,
        height=120,
    )
    document["objects"][0]["layout"] = {
        "mode": "horizontal",
        "padding": {"left": 20, "top": 10, "right": 30, "bottom": 10},
        "gap": 15,
        "main_alignment": "center",
        "cross_alignment": "center",
    }
    document, first = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=50,
        height=20,
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=70,
        height=40,
    )

    geometry = resolve_ui_constraints(document)
    assert geometry[first["id"]] == {
        "x": 227.5,
        "y": 100.0,
        "width": 50.0,
        "height": 20.0,
    }
    assert geometry[second["id"]] == {
        "x": 292.5,
        "y": 90.0,
        "width": 70.0,
        "height": 40.0,
    }


def test_vertical_auto_layout_stretches_cross_axis_and_skips_absolute_child() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, parent = add_ui_object(
        document,
        kind="group",
        x=10,
        y=20,
        width=200,
        height=300,
    )
    document["objects"][0]["layout"] = {
        "mode": "vertical",
        "padding": {"left": 10, "top": 20, "right": 30, "bottom": 40},
        "gap": 10,
        "main_alignment": "end",
        "cross_alignment": "stretch",
    }
    document, first = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=80,
        height=50,
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=90,
        height=60,
    )
    document, absolute = add_ui_object(
        document,
        kind="ellipse",
        parent_id=parent["id"],
        x=400,
        y=420,
        width=30,
        height=30,
    )
    document["objects"][-1]["layout"] = {"positioning": "absolute"}

    geometry = resolve_ui_constraints(document)
    assert geometry[first["id"]] == {
        "x": 20.0,
        "y": 160.0,
        "width": 160.0,
        "height": 50.0,
    }
    assert geometry[second["id"]] == {
        "x": 20.0,
        "y": 220.0,
        "width": 160.0,
        "height": 60.0,
    }
    assert geometry[absolute["id"]] == {
        "x": 400.0,
        "y": 420.0,
        "width": 30.0,
        "height": 30.0,
    }


def test_auto_layout_wraps_children_into_stable_rows() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(400, 300)
    document, parent = add_ui_object(
        document,
        kind="frame",
        width=250,
        height=120,
    )
    document["objects"][0]["layout"] = {
        "mode": "horizontal",
        "padding": 10,
        "gap": 10,
        "cross_gap": 24,
        "wrap": True,
    }
    child_ids: list[str] = []
    for _index in range(3):
        document, child = add_ui_object(
            document,
            kind="rectangle",
            parent_id=parent["id"],
            width=100,
            height=20,
        )
        child_ids.append(child["id"])

    geometry = resolve_ui_constraints(document)
    assert (geometry[child_ids[0]]["x"], geometry[child_ids[0]]["y"]) == (
        10.0,
        10.0,
    )
    assert (geometry[child_ids[1]]["x"], geometry[child_ids[1]]["y"]) == (
        120.0,
        10.0,
    )
    assert (geometry[child_ids[2]]["x"], geometry[child_ids[2]]["y"]) == (
        10.0,
        54.0,
    )


def test_auto_layout_hugs_content_and_distributes_fill_children() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, hug_parent = add_ui_object(
        document,
        kind="frame",
        x=20,
        y=30,
        width=500,
        height=200,
    )
    document["objects"][0]["layout"] = {
        "mode": "horizontal",
        "padding": {"left": 5, "top": 4, "right": 5, "bottom": 6},
        "gap": 10,
        "width_sizing": "hug",
        "height_sizing": "hug",
    }
    document, first = add_ui_object(
        document,
        kind="rectangle",
        parent_id=hug_parent["id"],
        width=50,
        height=20,
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        parent_id=hug_parent["id"],
        width=70,
        height=40,
    )
    geometry = resolve_ui_constraints(document)
    assert geometry[hug_parent["id"]]["width"] == 140.0
    assert geometry[hug_parent["id"]]["height"] == 50.0
    assert geometry[first["id"]]["x"] == 25.0
    assert geometry[second["id"]]["x"] == 85.0

    fill_document = create_ui_document(400, 200)
    fill_document, fill_parent = add_ui_object(
        fill_document,
        kind="frame",
        width=300,
        height=80,
    )
    fill_document["objects"][0]["layout"] = {
        "mode": "horizontal",
        "padding": 10,
        "gap": 10,
    }
    fill_document, fixed = add_ui_object(
        fill_document,
        kind="rectangle",
        parent_id=fill_parent["id"],
        width=50,
        height=20,
    )
    fill_ids: list[str] = []
    for _index in range(2):
        fill_document, child = add_ui_object(
            fill_document,
            kind="rectangle",
            parent_id=fill_parent["id"],
            width=20,
            height=20,
        )
        fill_document["objects"][-1]["layout"] = {"width_sizing": "fill"}
        fill_ids.append(child["id"])
    fill_geometry = resolve_ui_constraints(fill_document)
    assert fill_geometry[fixed["id"]]["width"] == 50.0
    assert fill_geometry[fill_ids[0]]["width"] == 105.0
    assert fill_geometry[fill_ids[1]]["width"] == 105.0
    assert fill_geometry[fill_ids[0]]["x"] == 70.0
    assert fill_geometry[fill_ids[1]]["x"] == 185.0


def test_fill_distribution_redistributes_after_max_constraint() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, parent = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        width=300,
        height=100,
    )
    document["objects"][-1]["layout"] = {
        "mode": "horizontal",
        "gap": 10,
    }
    document, capped = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=20,
        height=20,
    )
    document["objects"][-1]["layout"] = {"width_sizing": "fill"}
    document["objects"][-1]["constraints"]["max_width"] = 80
    document, flexible = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=20,
        height=20,
    )
    document["objects"][-1]["layout"] = {"width_sizing": "fill"}

    geometry = resolve_ui_constraints(document)
    assert geometry[capped["id"]]["width"] == 80.0
    assert geometry[flexible["id"]]["width"] == 210.0
    assert geometry[flexible["id"]]["x"] == 90.0


def test_sizing_control_discloses_hug_and_fill_only_in_valid_context() -> None:
    app = _app()
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
    )
    from app.painter_ui_inspector import PainterUIInspector

    document, parent = add_ui_object(
        create_ui_document(),
        kind="frame",
        width=300,
        height=100,
    )
    document["objects"][-1]["layout"] = {"mode": "horizontal"}
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=20,
        height=20,
    )
    inspector = PainterUIInspector()

    inspector.set_document(select_ui_object(document, parent["id"]))
    assert inspector.auto_layout_width_sizing_control.option_enabled("hug")
    assert not inspector.auto_layout_width_sizing_control.option_enabled("fill")

    inspector.set_document(select_ui_object(document, child["id"]))
    assert not inspector.auto_layout_width_sizing_control.option_enabled("hug")
    assert inspector.auto_layout_width_sizing_control.option_enabled("fill")

    document["objects"][-1]["layout"] = {"positioning": "absolute"}
    inspector.set_document(select_ui_object(document, child["id"]))
    assert not inspector.auto_layout_width_sizing_control.option_enabled("fill")
    inspector.deleteLater()
    app.processEvents()


def test_inspector_emits_auto_layout_properties() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document()
    document, row = add_ui_object(document, kind="frame", name="Toolbar")
    inspector = PainterUIInspector()
    inspector.set_document(document)
    inspector.show()
    app.processEvents()
    emitted: list[dict] = []
    inspector.properties_changed.connect(
        lambda _object_id, changes: emitted.append(changes)
    )
    assert inspector.auto_layout_mode_combo.isHidden()
    inspector.auto_layout_horizontal_button.click()
    assert inspector.auto_layout_horizontal_button.isChecked()
    inspector.auto_layout_vertical_button.click()
    assert inspector.auto_layout_vertical_button.isChecked()
    inspector.auto_layout_horizontal_button.click()
    for edge, value in {
        "left": 16,
        "top": 8,
        "right": 16,
        "bottom": 8,
    }.items():
        inspector.auto_layout_padding_controls[edge].setValue(value)
    inspector.auto_layout_gap_spin.setValue(12)
    inspector.auto_layout_cross_gap_spin.setValue(18)
    inspector.auto_layout_main_combo.setCurrentIndex(
        inspector.auto_layout_main_combo.findData("space_between")
    )
    inspector.auto_layout_cross_combo.setCurrentIndex(
        inspector.auto_layout_cross_combo.findData("center")
    )
    inspector.auto_layout_wrap_check.setChecked(True)
    inspector.auto_layout_width_sizing_combo.setCurrentIndex(
        inspector.auto_layout_width_sizing_combo.findData("hug")
    )
    inspector.auto_layout_height_sizing_combo.setCurrentIndex(
        inspector.auto_layout_height_sizing_combo.findData("fixed")
    )
    inspector._emit_properties()

    assert emitted[-1]["layout"] == {
        "mode": "horizontal",
        "padding": {"left": 16.0, "top": 8.0, "right": 16.0, "bottom": 8.0},
        "gap": 12.0,
        "cross_gap": 18.0,
        "main_alignment": "space_between",
        "cross_alignment": "center",
        "positioning": "auto",
        "wrap": True,
        "width_sizing": "hug",
        "height_sizing": "fixed",
        "grid_columns": 2,
        "grid_column_span": 1,
        "grid_row_span": 1,
        "cell_horizontal_alignment": "stretch",
        "cell_vertical_alignment": "stretch",
    }
    assert row["id"] == document["selection"]["object_id"]
    inspector.deleteLater()
    app.processEvents()


def test_grid_auto_layout_places_children_and_respects_spans() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, parent = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        x=20,
        y=30,
        width=330,
        height=230,
    )
    document["objects"][-1]["layout"] = {
        "mode": "grid",
        "grid_columns": 3,
        "padding": 10,
        "gap": 5,
        "cross_gap": 10,
    }
    child_ids: list[str] = []
    for index in range(4):
        document, child = add_ui_object(
            document,
            kind="rectangle",
            parent_id=parent["id"],
            width=20,
            height=20,
        )
        if index == 0:
            document["objects"][-1]["layout"] = {
                "grid_column_span": 2,
                "cell_horizontal_alignment": "stretch",
                "cell_vertical_alignment": "stretch",
            }
        child_ids.append(child["id"])

    geometry = resolve_ui_constraints(document)
    assert geometry[child_ids[0]] == {
        "x": 30.0,
        "y": 40.0,
        "width": 205.0,
        "height": 100.0,
    }
    assert geometry[child_ids[1]]["x"] == 240.0
    assert geometry[child_ids[2]]["x"] == 30.0
    assert geometry[child_ids[2]]["y"] == 150.0
    assert geometry[child_ids[3]]["x"] == 135.0


def test_nested_auto_layout_and_ignore_flow_constraints_follow_final_parent() -> None:
    from app.painter_ui_constraints import capture_ui_constraints, resolve_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, outer = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        x=100,
        y=80,
        width=400,
        height=220,
    )
    document["objects"][-1]["layout"] = {
        "mode": "horizontal",
        "padding": 10,
        "gap": 10,
    }
    document, nested = add_ui_object(
        document,
        kind="frame",
        parent_id=outer["id"],
        x=0,
        y=0,
        width=100,
        height=180,
    )
    document["objects"][-1]["layout"] = {
        "mode": "vertical",
        "padding": 10,
        "gap": 5,
        "cross_alignment": "stretch",
        "width_sizing": "fill",
    }
    document, sibling = add_ui_object(
        document,
        kind="rectangle",
        parent_id=outer["id"],
        width=80,
        height=40,
    )
    document, flow_child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=nested["id"],
        width=40,
        height=30,
    )
    document, ignored = add_ui_object(
        document,
        kind="rectangle",
        parent_id=nested["id"],
        x=20,
        y=100,
        width=30,
        height=20,
    )
    nested_source = next(row for row in document["objects"] if row["id"] == nested["id"])
    ignored_source = document["objects"][-1]
    ignored_source["layout"] = {"positioning": "absolute"}
    ignored_source["constraints"] = capture_ui_constraints(
        ignored_source,
        nested_source,
        {"horizontal": "right", "vertical": "bottom"},
    )

    geometry = resolve_ui_constraints(document)
    assert geometry[nested["id"]]["x"] == 110.0
    assert geometry[nested["id"]]["width"] == 290.0
    assert geometry[sibling["id"]]["x"] == 410.0
    assert geometry[flow_child["id"]]["x"] == 120.0
    assert geometry[flow_child["id"]]["width"] == 270.0
    assert geometry[ignored["id"]]["x"] == 320.0
    assert geometry[ignored["id"]]["y"] == 190.0


def test_inspector_discloses_grid_columns_and_child_spans() -> None:
    app = _app()
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
    )
    from app.painter_ui_inspector import PainterUIInspector

    document, parent = add_ui_object(create_ui_document(), kind="frame")
    document["objects"][-1]["layout"] = {
        "mode": "grid",
        "grid_columns": 4,
    }
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
    )
    document["objects"][-1]["layout"] = {
        "grid_column_span": 2,
        "grid_row_span": 3,
    }
    inspector = PainterUIInspector()

    inspector.set_document(select_ui_object(document, parent["id"]))
    inspector.show()
    app.processEvents()
    assert inspector.auto_layout_grid_button.isChecked()
    assert not inspector.auto_layout_grid_columns_spin.isHidden()
    assert inspector.auto_layout_grid_columns_spin.value() == 4
    assert inspector.auto_layout_grid_column_span_spin.isHidden()

    inspector.set_document(select_ui_object(document, child["id"]))
    app.processEvents()
    assert inspector.auto_layout_grid_columns_spin.isHidden()
    assert not inspector.auto_layout_grid_column_span_spin.isHidden()
    assert inspector.auto_layout_grid_column_span_spin.value() == 2
    assert inspector.auto_layout_grid_row_span_spin.value() == 3
    inspector.deleteLater()
    app.processEvents()


def test_inspector_names_ignore_auto_layout_and_keeps_nested_parent_controls() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document, select_ui_object
    from app.painter_ui_inspector import PainterUIInspector

    document, parent = add_ui_object(create_ui_document(), kind="frame")
    document["objects"][-1]["layout"] = {"mode": "horizontal"}
    document, nested = add_ui_object(
        document, kind="frame", parent_id=parent["id"]
    )
    document["objects"][-1]["layout"] = {
        "mode": "vertical",
        "width_sizing": "fill",
        "height_sizing": "hug",
    }
    inspector = PainterUIInspector()
    inspector.set_document(select_ui_object(document, nested["id"]))
    app.processEvents()

    assert inspector.auto_layout_positioning_combo.itemText(0) == "In flow"
    assert inspector.auto_layout_positioning_combo.itemText(1) == "Ignore auto layout"
    assert inspector.auto_layout_width_sizing_control.option_enabled("fill")
    assert inspector.auto_layout_height_sizing_control.option_enabled("hug")
    assert inspector.auto_layout_vertical_button.isChecked()
    inspector.deleteLater()
    app.processEvents()


def test_inspector_alignment_grid_auto_gap_and_wrap_disclosure() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document, _row = add_ui_object(
        create_ui_document(),
        kind="frame",
        name="Wrapping row",
    )
    inspector = PainterUIInspector()
    inspector.set_document(document)
    inspector.show()
    app.processEvents()
    emitted: list[dict] = []
    inspector.properties_changed.connect(
        lambda _object_id, changes: emitted.append(changes)
    )
    inspector.auto_layout_horizontal_button.click()
    assert inspector.auto_layout_wrap_check.isHidden() is False
    inspector.auto_layout_gap_auto_button.click()
    assert emitted[-1]["layout"]["main_alignment"] == "space_between"
    assert inspector.auto_layout_gap_spin.isEnabled() is False

    inspector.auto_layout_gap_auto_button.click()
    inspector.auto_layout_alignment_buttons[(2, 2)].click()
    assert emitted[-1]["layout"]["main_alignment"] == "end"
    assert emitted[-1]["layout"]["cross_alignment"] == "end"
    inspector.auto_layout_wrap_check.setChecked(True)
    inspector._sync_auto_layout_control_states()
    assert inspector.auto_layout_cross_gap_spin.isHidden() is False

    inspector.auto_layout_vertical_button.click()
    assert inspector.auto_layout_wrap_check.isHidden()
    assert emitted[-1]["layout"]["wrap"] is False
    inspector.deleteLater()
    app.processEvents()


def test_auto_layout_action_uses_object_update_and_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._add_default_painter_ui_object("frame")
    row = dialog._painter_ui_document["objects"][-1]
    original = dict(row["layout"])
    registry = ActionRegistry(owner=dialog)
    assert "paint.ui.layout.set" in {
        action["id"] for action in registry.list_actions()
    }
    result = registry.execute(
        "paint.ui.layout.set",
        {
            "object_id": row["id"],
            "mode": "vertical",
            "padding": {"left": 20, "top": 12, "right": 20, "bottom": 12},
            "gap": 10,
            "cross_gap": 16,
            "main_alignment": "center",
            "cross_alignment": "stretch",
            "wrap": True,
            "width_sizing": "hug",
            "height_sizing": "fixed",
        },
    ).to_dict()

    assert result["ok"] is True
    changed = result["result"]["ui_design"]["document"]["objects"][-1]
    assert changed["layout"]["mode"] == "vertical"
    assert changed["layout"]["gap"] == 10.0
    assert changed["layout"]["cross_gap"] == 16.0
    assert changed["layout"]["wrap"] is True
    assert changed["layout"]["width_sizing"] == "hug"
    dialog._undo()
    assert dialog._painter_ui_document["objects"][-1]["layout"] == original
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_canvas_auto_layout_controls_enable_and_drag_gap() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        x=120,
        y=120,
        width=360,
        height=180,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    overlay.set_tool("select")
    overlay.show()
    app.processEvents()
    changes: list[tuple[str, dict]] = []
    overlay.object_changes_requested.connect(
        lambda object_id, payload: changes.append((object_id, payload))
    )

    controls = overlay._auto_layout_canvas_controls()
    assert controls is not None
    horizontal = controls.control("mode_horizontal")
    assert horizontal is not None
    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        horizontal.rect.center().toPoint(),
    )
    assert changes[-1][0] == row["id"]
    assert changes[-1][1]["layout"]["mode"] == "horizontal"

    controls = overlay._auto_layout_canvas_controls()
    assert controls is not None
    gap = controls.control("gap")
    assert gap is not None
    start = gap.rect.center().toPoint()
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        start,
    )
    QTest.mouseMove(overlay, start + QPoint(30, 0))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        start + QPoint(30, 0),
    )
    assert changes[-1][1]["layout"]["gap"] > 0.0
    overlay.deleteLater()
    app.processEvents()


def test_canvas_spacing_drag_follows_axis_and_modifier_contract() -> None:
    from PySide6.QtCore import QPointF

    from app.painter_ui_auto_layout_overlay import (
        apply_auto_layout_canvas_click,
        apply_auto_layout_canvas_drag,
    )

    vertical = {
        "mode": "vertical",
        "gap": 8,
        "padding": {"left": 4, "top": 5, "right": 6, "bottom": 7},
        "wrap": True,
    }
    vertical = apply_auto_layout_canvas_click(vertical, "mode_vertical")
    assert vertical["wrap"] is False
    unchanged_x = apply_auto_layout_canvas_drag(
        vertical,
        "gap",
        QPointF(30, 0),
        scale=1.0,
    )
    assert unchanged_x["gap"] == 8.0
    changed_y = apply_auto_layout_canvas_drag(
        vertical,
        "gap",
        QPointF(0, 17),
        scale=1.0,
    )
    assert changed_y["gap"] == 25.0
    big_nudge = apply_auto_layout_canvas_drag(
        vertical,
        "gap",
        QPointF(0, 14),
        scale=1.0,
        big_nudge=True,
    )
    assert big_nudge["gap"] == 18.0

    opposite = apply_auto_layout_canvas_drag(
        vertical,
        "padding_left",
        QPointF(10, 0),
        scale=1.0,
        opposite=True,
    )
    assert opposite["padding"] == {
        "left": 14.0,
        "top": 5.0,
        "right": 16.0,
        "bottom": 7.0,
    }
    all_sides = apply_auto_layout_canvas_drag(
        vertical,
        "padding_top",
        QPointF(0, 10),
        scale=1.0,
        all_sides=True,
    )
    assert all_sides["padding"] == {
        "left": 14.0,
        "top": 15.0,
        "right": 16.0,
        "bottom": 17.0,
    }
    grid = apply_auto_layout_canvas_click(vertical, "mode_grid")
    assert grid["mode"] == "grid"
    grid_gap = apply_auto_layout_canvas_drag(
        grid,
        "gap",
        QPointF(12, 40),
        scale=1.0,
    )
    assert grid_gap["gap"] == 20.0


def test_wrap_exposes_second_gap_only_for_horizontal_flow() -> None:
    from PySide6.QtCore import QRectF

    from app.painter_ui_auto_layout_overlay import (
        build_auto_layout_canvas_controls,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, row = add_ui_object(
        create_ui_document(),
        kind="frame",
        width=300,
        height=200,
    )
    document["objects"][-1]["layout"] = {
        "mode": "horizontal",
        "wrap": True,
        "gap": 8,
        "cross_gap": 12,
    }
    controls = build_auto_layout_canvas_controls(
        document["objects"][-1],
        QRectF(100, 100, 300, 200),
        document,
        QRectF(0, 0, 900, 700),
        scale=1.0,
    )
    assert controls is not None
    assert controls.control("cross_gap") is not None
    document["objects"][-1]["layout"]["mode"] = "vertical"
    controls = build_auto_layout_canvas_controls(
        document["objects"][-1],
        QRectF(100, 100, 300, 200),
        document,
        QRectF(0, 0, 900, 700),
        scale=1.0,
    )
    assert controls is not None
    assert controls.control("cross_gap") is None


def test_auto_layout_entry_wraps_sibling_selection_in_frame() -> None:
    from app.painter_ui_auto_layout_entry import add_auto_layout_to_selection
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_objects,
    )

    document = create_ui_document(800, 600)
    document, first = add_ui_object(
        document, kind="rectangle", x=100, y=80, width=80, height=40
    )
    document, second = add_ui_object(
        document, kind="text", x=200, y=80, width=120, height=40
    )
    document = select_ui_objects(
        document,
        [first["id"], second["id"]],
        primary_object_id=second["id"],
    )

    updated, report = add_auto_layout_to_selection(document)

    assert report["operation"] == "wrap"
    assert report["created_frame"] is True
    frame = next(
        row for row in updated["objects"] if row["id"] == report["frame_id"]
    )
    assert frame["kind"] == "frame"
    assert frame["layout"]["mode"] == "horizontal"
    assert frame["layout"]["gap"] == 20.0
    assert (frame["x"], frame["y"], frame["width"], frame["height"]) == (
        100.0,
        80.0,
        220.0,
        40.0,
    )
    assert [
        row["id"]
        for row in sorted(updated["objects"], key=lambda row: row["z_index"])
        if row["parent_id"] == frame["id"]
    ] == [first["id"], second["id"]]
    assert updated["selection"] == {
        "object_id": frame["id"],
        "object_ids": [frame["id"]],
    }


def test_auto_layout_entry_applies_to_frame_and_remove_keeps_frame() -> None:
    from app.painter_ui_auto_layout_entry import (
        add_auto_layout_to_selection,
        remove_auto_layout_from_selection,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, frame = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        x=100,
        y=100,
        width=300,
        height=200,
    )
    document, _child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
        x=120,
        y=130,
        width=80,
        height=40,
    )
    document["selection"] = {
        "object_id": frame["id"],
        "object_ids": [frame["id"]],
    }

    applied, report = add_auto_layout_to_selection(document)
    assert report["created_frame"] is False
    assert len(applied["objects"]) == 2
    selected_frame = next(row for row in applied["objects"] if row["id"] == frame["id"])
    assert selected_frame["layout"]["mode"] == "horizontal"

    removed, remove_report = remove_auto_layout_from_selection(applied)
    assert remove_report["removed_frame_ids"] == [frame["id"]]
    assert len(removed["objects"]) == 2
    selected_frame = next(row for row in removed["objects"] if row["id"] == frame["id"])
    assert selected_frame["layout"]["mode"] == "none"
    assert any(row["parent_id"] == frame["id"] for row in removed["objects"])


def test_auto_layout_entry_shortcuts_emit_canonical_commands() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 480)
    overlay.show()
    overlay.setFocus()
    app.processEvents()
    commands: list[str] = []
    overlay.key_command.connect(
        lambda command, _coarse: commands.append(command)
    )

    QTest.keyClick(overlay, Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClick(
        overlay,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier,
    )

    assert commands == ["add_auto_layout", "remove_auto_layout"]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_auto_layout_entry_dialog_command_is_one_undo_step() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import select_ui_objects

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._add_default_painter_ui_object("rectangle")
    first = dialog._painter_ui_document["objects"][-1]["id"]
    dialog._add_default_painter_ui_object("text")
    second = dialog._painter_ui_document["objects"][-1]["id"]
    dialog._painter_ui_document = select_ui_objects(
        dialog._painter_ui_document,
        [first, second],
        primary_object_id=second,
    )
    object_count = len(dialog._painter_ui_document["objects"])

    result = dialog._apply_painter_ui_auto_layout_entry("add")
    assert result["ok"] is True
    assert len(dialog._painter_ui_document["objects"]) == object_count + 1
    dialog._undo()
    assert len(dialog._painter_ui_document["objects"]) == object_count
    assert set(dialog._painter_ui_document["selection"]["object_ids"]) == {
        first,
        second,
    }
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_inspector_auto_layout_entry_button_emits_selection_command() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document, _row = add_ui_object(
        create_ui_document(), kind="rectangle", name="Card"
    )
    inspector = PainterUIInspector()
    inspector.set_document(document)
    commands: list[str] = []
    inspector.auto_layout_entry_requested.connect(commands.append)
    inspector.auto_layout_add_button.click()

    assert commands == ["add"]
    assert inspector.auto_layout_add_button.toolTip() == "Add Auto Layout (Shift+A)"
    inspector.deleteLater()
    app.processEvents()


def test_canvas_auto_layout_controls_adjust_padding_and_child_positioning() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, parent = add_ui_object(
        create_ui_document(800, 600),
        kind="group",
        x=100,
        y=100,
        width=420,
        height=220,
    )
    document["objects"][-1]["layout"] = {
        "mode": "horizontal",
        "padding": 12,
        "gap": 10,
    }
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        x=0,
        y=0,
        width=100,
        height=80,
    )
    document = select_ui_object(document, parent["id"])
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    overlay.set_tool("select")
    overlay.show()
    app.processEvents()
    changes: list[tuple[str, dict]] = []
    overlay.object_changes_requested.connect(
        lambda object_id, payload: changes.append((object_id, payload))
    )

    controls = overlay._auto_layout_canvas_controls()
    assert controls is not None
    left = controls.control("padding_left")
    assert left is not None
    start = left.rect.center().toPoint()
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        start,
    )
    QTest.mouseMove(overlay, start + QPoint(24, 0))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        start + QPoint(24, 0),
    )
    assert changes[-1][1]["layout"]["padding"]["left"] > 12.0

    child_document = select_ui_object(overlay._document, child["id"])
    overlay.set_document(child_document)
    controls = overlay._auto_layout_canvas_controls()
    assert controls is not None
    positioning = controls.control("positioning")
    assert positioning is not None
    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        positioning.rect.center().toPoint(),
    )
    assert changes[-1][0] == child["id"]
    assert changes[-1][1]["layout"]["positioning"] == "absolute"
    overlay.deleteLater()
    app.processEvents()
