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
        "main_alignment": "space_between",
        "cross_alignment": "center",
        "positioning": "absolute",
        "wrap": False,
        "width_sizing": "fixed",
        "height_sizing": "fixed",
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
        40.0,
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


def test_inspector_emits_auto_layout_properties() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document()
    document, row = add_ui_object(document, kind="frame", name="Toolbar")
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[dict] = []
    inspector.properties_changed.connect(
        lambda _object_id, changes: emitted.append(changes)
    )
    inspector.auto_layout_mode_combo.setCurrentIndex(
        inspector.auto_layout_mode_combo.findData("horizontal")
    )
    for edge, value in {
        "left": 16,
        "top": 8,
        "right": 16,
        "bottom": 8,
    }.items():
        inspector.auto_layout_padding_controls[edge].setValue(value)
    inspector.auto_layout_gap_spin.setValue(12)
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
        "main_alignment": "space_between",
        "cross_alignment": "center",
        "positioning": "auto",
        "wrap": True,
        "width_sizing": "hug",
        "height_sizing": "fixed",
    }
    assert row["id"] == document["selection"]["object_id"]
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
    assert changed["layout"]["wrap"] is True
    assert changed["layout"]["width_sizing"] == "hug"
    dialog._undo()
    assert dialog._painter_ui_document["objects"][-1]["layout"] == original
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
