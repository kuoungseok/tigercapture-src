from __future__ import annotations

import json
import os

import pytest

from app.painter_ui_boolean import (
    compose_ui_boolean,
    flatten_ui_boolean,
    inspect_ui_boolean_selection,
    release_ui_boolean,
    set_ui_boolean,
)
from app.painter_ui_document import (
    PainterUIDocumentError,
    add_ui_object,
    normalize_ui_document,
    select_ui_objects,
    update_ui_object,
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
    grouped_rows = {row["id"]: row for row in document["objects"]}
    assert grouped_rows[first["id"]]["parent_id"] == group["id"]
    assert grouped_rows[second["id"]]["parent_id"] == group["id"]
    assert document["selection"]["object_ids"] == [group["id"]]
    assert inspect_ui_boolean_selection(document)["mode"] == "group"

    released = release_ui_boolean(document, group["id"])
    assert group["id"] not in {row["id"] for row in released["objects"]}
    assert {first["id"], second["id"]} <= {
        row["id"] for row in released["objects"]
    }
    assert released["selection"]["object_ids"] == [first["id"], second["id"]]
    released_rows = {row["id"]: row for row in released["objects"]}
    assert released_rows[first["id"]]["parent_id"] == ""
    assert released_rows[second["id"]]["parent_id"] == ""


def test_boolean_group_preserves_and_restores_a_nested_parent() -> None:
    document = normalize_ui_document(None, fallback_width=480, fallback_height=320)
    document, frame = add_ui_object(
        document,
        kind="frame",
        x=20,
        y=20,
        width=360,
        height=240,
    )
    document, first = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
        x=60,
        y=60,
        width=140,
        height=100,
    )
    document, second = add_ui_object(
        document,
        kind="ellipse",
        parent_id=frame["id"],
        x=130,
        y=80,
        width=120,
        height=90,
    )

    document, group = compose_ui_boolean(
        document,
        "union",
        [first["id"], second["id"]],
    )
    rows = {row["id"]: row for row in document["objects"]}
    assert rows[group["id"]]["parent_id"] == frame["id"]
    assert rows[first["id"]]["parent_id"] == group["id"]
    assert rows[second["id"]]["parent_id"] == group["id"]

    released = release_ui_boolean(document, group["id"])
    rows = {row["id"]: row for row in released["objects"]}
    assert rows[first["id"]]["parent_id"] == frame["id"]
    assert rows[second["id"]]["parent_id"] == frame["id"]


def test_boolean_edit_scope_reveals_operands_and_hides_result_host() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_workspace import PainterUIDesignOverlay

    app = QApplication.instance() or QApplication([])
    document, first, second = _two_shapes()
    document, group = compose_ui_boolean(
        document,
        "union",
        [first["id"], second["id"]],
    )
    overlay = PainterUIDesignOverlay()
    overlay.set_document(document)

    assert [row["id"] for row in overlay._visible_objects()] == [group["id"]]
    assert overlay.set_edit_scope(group["id"]) == group["id"]
    visible_ids = {row["id"] for row in overlay._visible_objects()}
    assert {first["id"], second["id"]} <= visible_ids
    assert group["id"] not in visible_ids

    selected_operand = select_ui_objects(
        document,
        [first["id"]],
        primary_object_id=first["id"],
    )
    overlay.set_edit_scope("")
    overlay.set_document(selected_operand)
    visible_ids = {row["id"] for row in overlay._visible_objects()}
    assert {first["id"], second["id"]} <= visible_ids
    assert group["id"] not in visible_ids
    app.processEvents()


def test_boolean_operand_inspector_locks_appearance_but_keeps_geometry() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_shape_selection_panel import PainterUIShapeSelectionPanel

    app = QApplication.instance() or QApplication([])
    document, first, second = _two_shapes()
    document, _group = compose_ui_boolean(
        document,
        "union",
        [first["id"], second["id"]],
    )
    rows = {row["id"]: row for row in document["objects"]}
    panel = PainterUIShapeSelectionPanel()
    panel.set_shape(rows[first["id"]], document)

    assert panel.geometry_controls["x"].isEnabled()
    assert panel.geometry_controls["width"].isEnabled()
    assert panel.radius_spin.isEnabled()
    assert panel.opacity_spin.isEnabled() is False
    assert panel.fill_editor.isEnabled() is False
    assert panel.stroke_editor.isEnabled() is False
    assert panel.effect_button.isEnabled() is False

    released = release_ui_boolean(document, _group["id"])
    released_rows = {row["id"]: row for row in released["objects"]}
    panel.set_shape(released_rows[first["id"]], released)
    assert panel.opacity_spin.isEnabled()
    assert panel.fill_editor.isEnabled()
    app.processEvents()


@pytest.mark.parametrize(
    ("operation", "expected_fill"),
    [
        ("union", "#222222FF"),
        ("subtract", "#111111FF"),
        ("intersect", "#222222FF"),
        ("exclude", "#222222FF"),
    ],
)
def test_boolean_group_inherits_the_figma_operation_style_source(
    operation: str,
    expected_fill: str,
) -> None:
    document = normalize_ui_document(None, fallback_width=480, fallback_height=320)
    document, bottom = add_ui_object(
        document,
        kind="rectangle",
        x=20,
        y=20,
        width=160,
        height=120,
        style={"fill": "#111111FF", "stroke": "#AA0000FF"},
    )
    document, top = add_ui_object(
        document,
        kind="ellipse",
        x=90,
        y=50,
        width=140,
        height=100,
        style={"fill": "#222222FF", "stroke": "#00AA00FF"},
    )

    _document, group = compose_ui_boolean(
        document,
        operation,
        [bottom["id"], top["id"]],
    )

    assert group["style"]["fill"] == expected_fill


def test_boolean_operand_contract_supports_text_and_rejects_frame() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    document = normalize_ui_document(None, fallback_width=480, fallback_height=320)
    document, shape = add_ui_object(
        document,
        kind="rectangle",
        x=20,
        y=20,
        width=160,
        height=120,
    )
    document, text = add_ui_object(
        document,
        kind="text",
        x=50,
        y=45,
        width=120,
        height=60,
        style={
            "text_color": "#3366CCFF",
            "font_family": "Arial",
            "font_size": 36,
            "font_weight": 700,
        },
        content={"text": "UI"},
    )
    document, group = compose_ui_boolean(
        document,
        "union",
        [shape["id"], text["id"]],
    )
    assert group["style"]["fill"] == "#3366CCFF"
    assert group["style"]["fills"][0]["color"] == "#3366CCFF"
    eligible = select_ui_objects(
        document,
        [shape["id"], text["id"]],
        primary_object_id=text["id"],
    )
    assert inspect_ui_boolean_selection(eligible)["eligible"] is True

    from PySide6.QtCore import QRectF
    from app.painter_ui_boolean_geometry import resolve_ui_boolean_path

    text_union_path = resolve_ui_boolean_path(
        document["objects"],
        group,
        lambda row: QRectF(
            float(row["x"]),
            float(row["y"]),
            float(row["width"]),
            float(row["height"]),
        ),
    )
    assert text_union_path is not None and not text_union_path.isEmpty()

    document, frame = add_ui_object(
        document,
        kind="frame",
        x=240,
        y=20,
        width=120,
        height=100,
    )
    document, sibling_shape = add_ui_object(
        document,
        kind="rectangle",
        x=210,
        y=150,
        width=80,
        height=60,
    )
    with pytest.raises(PainterUIDocumentError, match="Unsupported"):
        compose_ui_boolean(
            document,
            "union",
            [sibling_shape["id"], frame["id"]],
        )
    ineligible = select_ui_objects(
        document,
        [sibling_shape["id"], frame["id"]],
        primary_object_id=frame["id"],
    )
    report = inspect_ui_boolean_selection(ineligible)
    assert report["eligible"] is False
    assert report["reason"] == "unsupported_kind"
    app.processEvents()


@pytest.mark.parametrize("kind", ["polygon", "star", "arc"])
def test_parametric_boolean_group_can_change_operation(kind: str) -> None:
    document = normalize_ui_document(None, fallback_width=480, fallback_height=320)
    document, first = add_ui_object(
        document,
        kind=kind,
        x=20,
        y=20,
        width=160,
        height=120,
    )
    document, second = add_ui_object(
        document,
        kind="ellipse",
        x=90,
        y=50,
        width=140,
        height=100,
    )
    document, group = compose_ui_boolean(
        document,
        "union",
        [first["id"], second["id"]],
    )

    document, updated = set_ui_boolean(
        document,
        group["id"],
        "exclude",
        [first["id"], second["id"]],
        group=True,
    )

    assert updated["content"]["boolean"]["operation"] == "exclude"


def test_m1b1_boolean_document_round_trip_preserves_operation_order_and_style() -> None:
    document, first, second = _two_shapes()
    document, group = compose_ui_boolean(
        document,
        "subtract",
        [first["id"], second["id"]],
    )

    restored = normalize_ui_document(
        json.loads(json.dumps(document, ensure_ascii=False))
    )
    restored_group = next(
        row for row in restored["objects"] if row["id"] == group["id"]
    )

    assert restored_group["content"]["boolean"] == group["content"]["boolean"]
    assert restored_group["style"]["fill"] == first["style"]["fill"]


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
    assert base_pixel.alpha() > 0 and base_pixel.blue() > base_pixel.red()
    assert cut_pixel.name().lower() == "#ffffff"

    svg, blocked = _svg_for_artboard(
        document,
        document["artboards"][0],
    )
    assert blocked == []
    assert group["id"] not in svg
    assert svg.count("<path ") == 1
    assert "data:image/png" not in svg


def test_m1b7_editable_svg_rerender_matches_canvas_within_tolerance() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    from app.painter_ui_asset_export import _svg_for_artboard, render_ui_artboard

    document, first, second = _two_shapes()
    document, _group = compose_ui_boolean(
        document,
        "subtract",
        [first["id"], second["id"]],
    )
    canvas = render_ui_artboard(document, document["active_artboard_id"])
    svg, blocked = _svg_for_artboard(document, document["artboards"][0])
    assert blocked == []
    assert "data:image/png" not in svg

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    assert renderer.isValid()
    rerendered = QImage(
        canvas.width(),
        canvas.height(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    rerendered.fill(QColor("#00000000"))
    painter = QPainter(rerendered)
    renderer.render(painter)
    painter.end()

    compared = canvas.width() * canvas.height()
    different = 0
    for y in range(canvas.height()):
        for x in range(canvas.width()):
            left = canvas.pixelColor(x, y)
            right = rerendered.pixelColor(x, y)
            if max(
                abs(left.red() - right.red()),
                abs(left.green() - right.green()),
                abs(left.blue() - right.blue()),
                abs(left.alpha() - right.alpha()),
            ) > 24:
                different += 1
    assert different / compared < 0.02, {
        "canvas_origin": canvas.pixelColor(0, 0).name(QColor.NameFormat.HexArgb),
        "svg_origin": rerendered.pixelColor(0, 0).name(QColor.NameFormat.HexArgb),
        "canvas_center": canvas.pixelColor(240, 160).name(QColor.NameFormat.HexArgb),
        "svg_center": rerendered.pixelColor(240, 160).name(QColor.NameFormat.HexArgb),
        "svg_head": svg[:240],
    }


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


@pytest.mark.parametrize(
    ("alignment", "expected_left", "expected_width"),
    [
        ("inside", 50.0, 100.0),
        ("center", 45.0, 110.0),
        ("outside", 40.0, 120.0),
    ],
)
def test_m1b2_boolean_geometry_includes_visible_stroke_alignment(
    alignment: str,
    expected_left: float,
    expected_width: float,
) -> None:
    from PySide6.QtCore import QRectF

    from app.painter_ui_boolean_geometry import ui_object_boolean_geometry_path

    row = {
        "id": "stroke-only",
        "kind": "rectangle",
        "rotation": 0,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "style": {
            "fill": "#00000000",
            "fills": [],
            "stroke": "#FFFFFFFF",
            "stroke_width": 10,
            "stroke_align": alignment,
            "strokes": [
                {
                    "type": "solid",
                    "visible": True,
                    "opacity": 1.0,
                    "color": "#FFFFFFFF",
                    "width": 10,
                    "align": alignment,
                }
            ],
        },
        "content": {},
    }

    path = ui_object_boolean_geometry_path(
        row,
        QRectF(50.0, 50.0, 100.0, 100.0),
    )
    bounds = path.boundingRect()

    assert bounds.left() == pytest.approx(expected_left, abs=0.01)
    assert bounds.width() == pytest.approx(expected_width, abs=0.01)


def test_m1b5_nested_boolean_resolves_round_trips_and_releases() -> None:
    from PySide6.QtCore import QRectF

    from app.painter_ui_boolean_geometry import (
        qpath_to_svg_path,
        resolve_ui_boolean_path,
    )

    document, first, second = _two_shapes()
    document, inner = compose_ui_boolean(
        document,
        "union",
        [first["id"], second["id"]],
    )
    document, third = add_ui_object(
        document,
        kind="star",
        x=135,
        y=55,
        width=120,
        height=150,
    )
    document, outer = compose_ui_boolean(
        document,
        "exclude",
        [inner["id"], third["id"]],
    )
    rows = {row["id"]: row for row in document["objects"]}
    assert rows[inner["id"]]["parent_id"] == outer["id"]
    assert rows[first["id"]]["parent_id"] == inner["id"]

    rect_for = lambda row: QRectF(
        float(row["x"]),
        float(row["y"]),
        float(row["width"]),
        float(row["height"]),
    )
    path = resolve_ui_boolean_path(document["objects"], rows[outer["id"]], rect_for)
    assert path is not None and not path.isEmpty()
    signature = qpath_to_svg_path(path)

    restored = normalize_ui_document(json.loads(json.dumps(document)))
    restored_rows = {row["id"]: row for row in restored["objects"]}
    restored_path = resolve_ui_boolean_path(
        restored["objects"],
        restored_rows[outer["id"]],
        rect_for,
    )
    assert restored_path is not None
    assert qpath_to_svg_path(restored_path) == signature

    released = release_ui_boolean(restored, inner["id"])
    released_rows = {row["id"]: row for row in released["objects"]}
    assert inner["id"] not in released_rows
    outer_operands = released_rows[outer["id"]]["content"]["boolean"]["operand_ids"]
    assert outer_operands == [first["id"], second["id"], third["id"]]
    assert released_rows[first["id"]]["parent_id"] == outer["id"]
    released_path = resolve_ui_boolean_path(
        released["objects"],
        released_rows[outer["id"]],
        rect_for,
    )
    assert released_path is not None


def test_m1b5_four_level_nested_boolean_is_deterministic() -> None:
    from PySide6.QtCore import QRectF

    from app.painter_ui_boolean_geometry import (
        qpath_to_svg_path,
        resolve_ui_boolean_path,
    )

    document, first, second = _two_shapes()
    document, current = compose_ui_boolean(
        document, "union", [first["id"], second["id"]]
    )
    operations = ("subtract", "intersect", "exclude")
    for index, operation in enumerate(operations, start=1):
        document, sibling = add_ui_object(
            document,
            kind="ellipse" if index % 2 else "rectangle",
            x=45 + index * 30,
            y=50 + index * 18,
            width=210 - index * 20,
            height=145 - index * 10,
        )
        document, current = compose_ui_boolean(
            document,
            operation,
            [current["id"], sibling["id"]],
        )
    by_id = {row["id"]: row for row in document["objects"]}
    rect_for = lambda row: QRectF(
        float(row["x"]), float(row["y"]),
        float(row["width"]), float(row["height"]),
    )
    signatures = []
    for _ in range(3):
        path = resolve_ui_boolean_path(document["objects"], by_id[current["id"]], rect_for)
        assert path is not None
        signatures.append(qpath_to_svg_path(path))
    assert signatures[0] == signatures[1] == signatures[2]


def test_m1b5_boolean_cycle_is_rejected_without_mutating_document() -> None:
    document, first, second = _two_shapes()
    document, inner = compose_ui_boolean(
        document, "union", [first["id"], second["id"]]
    )
    document, third = add_ui_object(
        document,
        kind="ellipse",
        x=40,
        y=40,
        width=90,
        height=90,
    )
    document, outer = compose_ui_boolean(
        document, "subtract", [inner["id"], third["id"]]
    )
    before = json.dumps(document, sort_keys=True)

    with pytest.raises(PainterUIDocumentError, match="cycle"):
        set_ui_boolean(
            document,
            inner["id"],
            "union",
            [first["id"], outer["id"]],
            group=True,
        )

    assert json.dumps(document, sort_keys=True) == before


def test_m1b6_flatten_replaces_boolean_tree_with_one_editable_vector() -> None:
    from PySide6.QtCore import QPointF, QRectF

    from app.painter_ui_boolean_geometry import (
        resolve_ui_boolean_path,
        ui_object_shape_path,
    )

    document, first, second = _two_shapes()
    document, group = compose_ui_boolean(
        document,
        "subtract",
        [first["id"], second["id"]],
    )
    group_row = next(row for row in document["objects"] if row["id"] == group["id"])
    rect_for = lambda row: QRectF(
        float(row["x"]), float(row["y"]),
        float(row["width"]), float(row["height"]),
    )
    before = resolve_ui_boolean_path(document["objects"], group_row, rect_for)
    assert before is not None and not before.isEmpty()

    flattened_document, flattened = flatten_ui_boolean(document, group["id"])
    ids = {row["id"] for row in flattened_document["objects"]}
    assert group["id"] in ids
    assert first["id"] not in ids
    assert second["id"] not in ids
    assert flattened["kind"] == "path"
    assert flattened["content"]["boolean"]["enabled"] is False
    assert flattened["content"]["boolean"]["group"] is False
    assert flattened["content"]["converted_from_kind"] == "boolean"
    assert flattened["content"]["vector_network"]["nodes"]
    assert flattened_document["selection"]["object_id"] == group["id"]

    after = ui_object_shape_path(flattened, rect_for(flattened))
    before_bounds = before.boundingRect()
    after_bounds = after.boundingRect()
    assert after_bounds.left() == pytest.approx(before_bounds.left(), abs=0.01)
    assert after_bounds.top() == pytest.approx(before_bounds.top(), abs=0.01)
    assert after_bounds.width() == pytest.approx(before_bounds.width(), abs=0.01)
    assert after_bounds.height() == pytest.approx(before_bounds.height(), abs=0.01)
    for x, y in ((90, 90), (120, 150), (240, 145), (300, 180)):
        point = QPointF(x, y)
        assert after.contains(point) == before.contains(point)


def test_m1b6_flatten_cleans_operand_references_without_removing_result() -> None:
    from app.painter_ui_document import add_ui_interaction, validate_ui_document
    from app.painter_ui_sections import create_ui_section

    document, first, second = _two_shapes()
    document, group = compose_ui_boolean(
        document,
        "union",
        [first["id"], second["id"]],
    )
    document, _section = create_ui_section(
        document,
        {
            "name": "Boolean source",
            "object_ids": [group["id"], first["id"], second["id"]],
        },
    )
    document, _interaction = add_ui_interaction(
        document,
        source_object_id=first["id"],
        target_object_id=second["id"],
    )

    flattened_document, flattened = flatten_ui_boolean(document, group["id"])

    assert flattened["id"] == group["id"]
    assert flattened_document["sections"][0]["object_ids"] == [group["id"]]
    assert flattened_document["interactions"] == []
    assert validate_ui_document(flattened_document)["ok"]


def test_m1b8_workspace_caches_boolean_geometry_until_render_state_changes(
    monkeypatch,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import app.painter_ui_boolean_geometry as geometry
    from app.painter_ui_workspace import PainterUIDesignOverlay

    _app = QApplication.instance() or QApplication([])
    document, first, second = _two_shapes()
    document, group = compose_ui_boolean(
        document,
        "union",
        [first["id"], second["id"]],
    )
    calls = 0
    original = geometry.resolve_ui_boolean_path

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(geometry, "resolve_ui_boolean_path", counted)
    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 480)
    overlay.set_document(document)
    row = overlay._effective_objects_by_id[group["id"]]

    assert overlay._boolean_path(row) is overlay._boolean_path(row)
    assert calls == 1

    overlay.set_motion_preview({first["id"]: {"x": 12.0}})
    assert overlay._boolean_path(row) is not None
    assert calls == 2

    document, _updated = update_ui_object(
        document,
        first["id"],
        {"x": float(first["x"]) + 8.0},
    )
    overlay.set_document(document)
    row = overlay._effective_objects_by_id[group["id"]]
    assert overlay._boolean_path(row) is not None
    assert calls == 3


def test_m1b8_boolean_context_bar_has_keyboard_and_accessibility_contract() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QWidget

    from app.painter_ui_boolean_context_bar import PainterUIBooleanContextBar

    _app = QApplication.instance() or QApplication([])
    parent = QWidget()
    bar = PainterUIBooleanContextBar(parent)
    bar.set_state(
        {
            "eligible": True,
            "mode": "group",
            "operation": "union",
            "operand_ids": ["first", "second"],
        }
    )

    assert bar.accessibleName()
    assert "2" in bar.accessibleDescription()
    for button in [
        *bar.operation_buttons.values(),
        bar.release_button,
        bar.flatten_button,
    ]:
        assert button.accessibleName()
        assert button.focusPolicy() & Qt.FocusPolicy.TabFocus


def test_m1b2_outside_stroke_matches_canvas_png_and_editable_svg() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor

    from app.painter_ui_asset_export import _svg_for_artboard, render_ui_artboard

    document = normalize_ui_document(None, fallback_width=480, fallback_height=320)
    document, stroked = add_ui_object(
        document,
        kind="rectangle",
        x=100,
        y=100,
        width=100,
        height=100,
        style={
            "fill": "#00000000",
            "fills": [],
            "stroke": "#FFFFFFFF",
            "stroke_width": 10,
            "stroke_align": "outside",
            "strokes": [
                {
                    "type": "solid",
                    "visible": True,
                    "opacity": 1.0,
                    "color": "#FFFFFFFF",
                    "width": 10,
                    "align": "outside",
                }
            ],
        },
    )
    document, style_source = add_ui_object(
        document,
        kind="ellipse",
        x=300,
        y=120,
        width=40,
        height=40,
        style={"fill": "#CC3344FF"},
    )
    document, _group = compose_ui_boolean(
        document,
        "union",
        [stroked["id"], style_source["id"]],
    )

    image = render_ui_artboard(document, document["active_artboard_id"])
    outside = QColor(image.pixel(92, 150))
    beyond = QColor(image.pixel(85, 150))
    assert outside.name().lower() != "#ffffff"
    assert beyond.name().lower() == "#ffffff"

    svg, blocked = _svg_for_artboard(document, document["artboards"][0])
    assert blocked == []
    assert svg.count("<path ") == 1
    assert "90.000000" in svg


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
    assert "Alt+Shift+U" in bar.operation_buttons["union"].toolTip()
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
    assert bar.flatten_button.isVisible()
    assert bar.operation_buttons["union"].isChecked()
    bar.release_button.click()
    assert commands[-1] == "release"
    bar.set_state({"eligible": False})
    assert bar.isHidden()
    parent.close()
    app.processEvents()


@pytest.mark.parametrize(
    ("key_name", "expected"),
    [
        ("U", "boolean_union"),
        ("S", "boolean_subtract"),
        ("I", "boolean_intersect"),
        ("E", "boolean_exclude"),
        ("F", "boolean_flatten"),
    ],
)
def test_boolean_windows_shortcuts_dispatch_from_the_canvas(
    key_name: str,
    expected: str,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_workspace import PainterUIDesignOverlay

    app = QApplication.instance() or QApplication([])
    overlay = PainterUIDesignOverlay()
    overlay.resize(480, 320)
    overlay.show()
    commands: list[str] = []
    overlay.key_command.connect(
        lambda command, _coarse: commands.append(command)
    )
    key = getattr(Qt.Key, f"Key_{key_name}")
    QTest.keyClick(
        overlay,
        key,
        Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.ShiftModifier,
    )
    assert commands == [expected]
    overlay.close()
    app.processEvents()


def test_outline_mode_exposes_nested_and_optionally_hidden_boolean_layers() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_document import update_ui_object
    from app.painter_ui_workspace import PainterUIDesignOverlay

    app = QApplication.instance() or QApplication([])
    document, first, second = _two_shapes()
    document, group = compose_ui_boolean(
        document, "union", [first["id"], second["id"]]
    )
    document, _hidden = update_ui_object(
        document, second["id"], {"visible": False}
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(480, 320)
    overlay.set_document(document)
    overlay.show()

    overlay.set_view_options(layer_outlines=True)
    outline_ids = {row["id"] for row in overlay._outline_objects()}
    assert group["id"] in outline_ids
    assert first["id"] in outline_ids
    assert second["id"] not in outline_ids
    overlay.set_view_options(
        outline_include_hidden=True,
        outline_include_bounds=True,
    )
    assert second["id"] in {row["id"] for row in overlay._outline_objects()}
    assert not overlay.grab().isNull()

    commands: list[str] = []
    overlay.key_command.connect(
        lambda command, _coarse: commands.append(command)
    )
    QTest.keyClick(
        overlay,
        Qt.Key.Key_O,
        Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.ShiftModifier,
    )
    assert commands[-1] == "toggle_layer_outlines"
    overlay.close()
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

    flattened = registry.execute(
        "paint.ui.vector.boolean.flatten",
        {"object_id": group_id},
    ).to_dict()
    assert flattened["ok"]
    assert flattened["result"]["object"]["kind"] == "path"
    assert dialog._undo_labels[-1] == "Flatten UI Boolean"

    dialog._undo()
    restored_group = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == group_id
    )
    assert restored_group["content"]["boolean"]["group"] is True

    dialog._undo()
    assert group_id not in {
        row["id"] for row in dialog._painter_ui_document["objects"]
    }
    assert {first, second} <= {
        row["id"] for row in dialog._painter_ui_document["objects"]
    }
    dialog.close()
    app.processEvents()
