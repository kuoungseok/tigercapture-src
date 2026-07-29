from __future__ import annotations

import os

from app.painter_ui_boolean import (
    compose_ui_boolean,
    inspect_ui_boolean_selection,
    release_ui_boolean,
)
from app.painter_ui_document import (
    add_ui_object,
    normalize_ui_document,
    select_ui_objects,
)


def _two_shapes():
    document = normalize_ui_document(
        None,
        fallback_width=480,
        fallback_height=320,
    )
    document, first = add_ui_object(
        document,
        kind="rectangle",
        name="Base",
        x=80,
        y=80,
        width=180,
        height=120,
        style={"fill": "#4F8FE8", "radius": 12},
    )
    document, second = add_ui_object(
        document,
        kind="ellipse",
        name="Cut",
        x=190,
        y=105,
        width=130,
        height=90,
        style={"fill": "#E8A74F"},
    )
    document = select_ui_objects(
        document,
        [first["id"], second["id"]],
        primary_object_id=second["id"],
    )
    return document, first, second


def test_compose_and_release_boolean_group_preserve_editable_operands() -> None:
    document, first, second = _two_shapes()
    report = inspect_ui_boolean_selection(document)
    assert report["eligible"]
    assert report["mode"] == "selection"

    document, group = compose_ui_boolean(
        document,
        "subtract",
        [first["id"], second["id"]],
    )
    stored = next(row for row in document["objects"] if row["id"] == group["id"])
    boolean = stored["content"]["boolean"]
    assert boolean["enabled"]
    assert boolean["group"]
    assert boolean["operation"] == "subtract"
    assert boolean["operand_ids"] == [first["id"], second["id"]]
    assert document["selection"]["object_ids"] == [group["id"]]
    assert inspect_ui_boolean_selection(document)["mode"] == "group"

    released = release_ui_boolean(document, group["id"])
    assert group["id"] not in {row["id"] for row in released["objects"]}
    assert {first["id"], second["id"]} <= {
        row["id"] for row in released["objects"]
    }
    assert released["selection"]["object_ids"] == [first["id"], second["id"]]


def test_boolean_png_and_svg_use_result_geometry_not_visible_operands() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor

    from app.painter_ui_asset_export import _svg_for_artboard, render_ui_artboard

    document, first, second = _two_shapes()
    document, group = compose_ui_boolean(
        document,
        "subtract",
        [first["id"], second["id"]],
    )
    image = render_ui_artboard(
        document,
        document["active_artboard_id"],
    )
    base_pixel = QColor(image.pixel(110, 120))
    cut_pixel = QColor(image.pixel(230, 145))
    assert base_pixel.alpha() > 0 and base_pixel.red() > base_pixel.blue()
    assert cut_pixel.name().lower() == "#ffffff"

    svg, blocked = _svg_for_artboard(
        document,
        document["artboards"][0],
    )
    assert blocked == []
    assert group["id"] not in svg
    assert svg.count("<path ") == 1
    assert "data:image/png" not in svg


def test_boolean_geometry_supports_vector_paths_and_exclude() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QRectF

    from app.painter_ui_boolean_geometry import (
        resolve_ui_boolean_path,
        ui_object_shape_path,
    )

    triangle = {
        "id": "triangle",
        "kind": "path",
        "x": 20,
        "y": 20,
        "width": 160,
        "height": 140,
        "rotation": 0,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "style": {},
        "content": {
            "vector_network": {
                "closed": True,
                "nodes": [
                    {"id": "a", "x": 0.5, "y": 0.0},
                    {"id": "b", "x": 1.0, "y": 1.0},
                    {"id": "c", "x": 0.0, "y": 1.0},
                ],
                "segments": [
                    {
                        "id": "ab",
                        "start_node_id": "a",
                        "end_node_id": "b",
                        "kind": "line",
                    },
                    {
                        "id": "bc",
                        "start_node_id": "b",
                        "end_node_id": "c",
                        "kind": "line",
                    },
                    {
                        "id": "ca",
                        "start_node_id": "c",
                        "end_node_id": "a",
                        "kind": "line",
                    },
                ],
            }
        },
    }
    ellipse = {
        "id": "ellipse",
        "kind": "ellipse",
        "x": 80,
        "y": 55,
        "width": 110,
        "height": 90,
        "rotation": 0,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "style": {},
        "content": {},
    }
    group = {
        "id": "boolean",
        "content": {
            "boolean": {
                "enabled": True,
                "group": True,
                "operation": "exclude",
                "operand_ids": ["triangle", "ellipse"],
            }
        },
    }
    rect_for = lambda row: QRectF(
        float(row["x"]),
        float(row["y"]),
        float(row["width"]),
        float(row["height"]),
    )
    source = ui_object_shape_path(triangle, rect_for(triangle))
    result = resolve_ui_boolean_path(
        [triangle, ellipse, group],
        group,
        rect_for,
    )

    assert source.contains(source.boundingRect().center())
    assert result is not None and not result.isEmpty()
    assert result.boundingRect().width() >= source.boundingRect().width()


def test_boolean_context_bar_is_transient_and_emits_icon_commands() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget

    from app.painter_ui_boolean_context_bar import PainterUIBooleanContextBar

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(640, 480)
    bar = PainterUIBooleanContextBar(parent)
    commands: list[str] = []
    bar.command_requested.connect(commands.append)
    bar.set_state(
        {
            "mode": "selection",
            "eligible": True,
            "selection_ids": ["shape-1", "shape-2"],
        }
    )
    parent.show()
    app.processEvents()
    assert bar.isVisible()
    assert bar.release_button.isHidden()
    bar.operation_buttons["union"].click()
    assert commands == ["union"]

    bar.set_state(
        {
            "mode": "group",
            "eligible": True,
            "selection_ids": ["boolean-1"],
            "group_id": "boolean-1",
            "operation": "union",
            "operand_ids": ["shape-1", "shape-2"],
        }
    )
    assert bar.release_button.isVisible()
    assert bar.operation_buttons["union"].isChecked()
    bar.release_button.click()
    assert commands[-1] == "release"
    bar.set_state({"eligible": False})
    assert bar.isHidden()
    parent.close()
    app.processEvents()


def test_boolean_action_uses_selection_and_one_step_undo() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(480, 320, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    first = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "rectangle",
            "x": 80,
            "y": 80,
            "width": 180,
            "height": 120,
            "style": {"fill": "#4F8FE8"},
        },
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    second = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "ellipse",
            "x": 190,
            "y": 105,
            "width": 130,
            "height": 90,
            "style": {"fill": "#E8A74F"},
        },
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    registry.execute(
        "paint.ui.selection.set",
        {"object_ids": [first, second], "primary_object_id": second},
    )
    composed = registry.execute(
        "paint.ui.vector.boolean.compose",
        {"operation": "subtract"},
    ).to_dict()
    assert composed["ok"]
    group_id = composed["result"]["object"]["id"]
    assert dialog._painter_ui_document["selection"]["object_id"] == group_id
    assert dialog._undo_labels[-1] == "Create UI Boolean group"

    dialog._undo()
    assert group_id not in {
        row["id"] for row in dialog._painter_ui_document["objects"]
    }
    assert {first, second} <= {
        row["id"] for row in dialog._painter_ui_document["objects"]
    }
    dialog.close()
    app.processEvents()
