from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _shape_document(kind: str, content: dict):
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(480, 320, name="Shapes")
    return add_ui_object(
        document,
        kind=kind,
        name=kind.title(),
        x=80,
        y=50,
        width=220,
        height=180,
        style={
            "fill": "#4C74DB",
            "stroke": "#D6E3FF",
            "stroke_width": 3,
        },
        content=content,
    )


def test_parametric_shape_content_normalizes_and_round_trips() -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_parametric_shapes import (
        normalize_parametric_shape_content,
    )

    assert normalize_parametric_shape_content(
        "star",
        {"point_count": 100, "inner_radius": -1, "rotation_offset": 999},
    ) == {
        "point_count": 60,
        "inner_radius": 0.05,
        "rotation_offset": 360.0,
        "corner_radius": 0.0,
    }
    document, row = _shape_document(
        "arc",
        {"start_angle": -45, "sweep_angle": 240, "inner_radius": 0.62},
    )
    restored = normalize_ui_document(document)
    saved = next(item for item in restored["objects"] if item["id"] == row["id"])
    assert saved["kind"] == "arc"
    assert saved["content"]["start_angle"] == -45.0
    assert saved["content"]["sweep_angle"] == 240.0
    assert saved["content"]["inner_radius"] == 0.62

    negative_document, negative_row = _shape_document(
        "arc",
        {"start_angle": 0, "sweep_angle": -292, "inner_radius": 0.0},
    )
    negative_saved = next(
        item
        for item in normalize_ui_document(negative_document)["objects"]
        if item["id"] == negative_row["id"]
    )
    assert negative_saved["content"]["sweep_angle"] == -292.0


def test_parametric_shape_paths_have_distinct_real_geometry() -> None:
    _app()
    from PySide6.QtCore import QPointF, QRectF

    from app.painter_ui_parametric_shapes import parametric_shape_path

    rect = QRectF(0, 0, 200, 160)
    polygon = parametric_shape_path(
        rect,
        "polygon",
        {"point_count": 6},
    )
    star = parametric_shape_path(
        rect,
        "star",
        {"point_count": 5, "inner_radius": 0.4},
    )
    arc = parametric_shape_path(
        rect,
        "arc",
        {"start_angle": -90, "sweep_angle": 270, "inner_radius": 0.55},
    )

    assert not polygon.isEmpty()
    assert not star.isEmpty()
    assert not arc.isEmpty()
    assert polygon.elementCount() != star.elementCount()
    assert not arc.contains(rect.center() + QPointF(0, -5))
    assert any(
        arc.elementAt(index).isCurveTo()
        for index in range(arc.elementCount())
    )

    negative_arc = parametric_shape_path(
        rect,
        "arc",
        {"start_angle": 0, "sweep_angle": -270, "inner_radius": 0.0},
    )
    assert negative_arc.contains(QPointF(50, 40))
    assert not negative_arc.contains(QPointF(150, 120))


def test_star_corner_radius_is_editable_from_shape_inspector() -> None:
    app = _app()
    from app.painter_ui_shape_selection_panel import (
        PainterUIShapeSelectionPanel,
    )

    document, row = _shape_document(
        "star",
        {
            "point_count": 7,
            "inner_radius": 0.38,
            "corner_radius": 0.0,
        },
    )
    panel = PainterUIShapeSelectionPanel()
    panel.set_shape(row, document)
    assert panel.points_spin.maximum() == 60
    assert panel.radius_spin.isHidden() is False
    changes: list[dict] = []
    panel.properties_changed.connect(lambda value: changes.append(dict(value)))
    panel.radius_spin.setValue(36.0)
    panel._emit_properties()
    assert changes[-1]["content"]["corner_radius"] == 36.0
    panel.deleteLater()
    app.processEvents()


def test_parametric_shapes_render_and_export_as_svg_paths() -> None:
    _app()
    from app.painter_ui_asset_export import _svg_for_artboard, render_ui_artboard

    document, _row = _shape_document(
        "star",
        {"point_count": 7, "inner_radius": 0.38},
    )
    artboard = document["artboards"][0]
    image = render_ui_artboard(document, artboard["id"])
    svg, blocked = _svg_for_artboard(document, artboard)

    assert not image.isNull()
    assert image.pixelColor(190, 140).alpha() > 0
    assert blocked == []
    assert '<path d="' in svg
    assert 'fill-rule="evenodd"' in svg


def test_parametric_shape_inspector_is_contextual_and_emits_content() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    document, row = _shape_document(
        "star",
        {"point_count": 5, "inner_radius": 0.45},
    )
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[tuple[str, dict]] = []
    inspector.properties_changed.connect(
        lambda object_id, changes: emitted.append((object_id, changes))
    )

    assert inspector.design_group_visible("shape")
    panel = inspector.shape_selection_panel
    assert inspector.selection_content_stack.currentWidget() is (
        inspector.shape_selection_scroll
    )
    assert panel.points_spin.isVisibleTo(inspector)
    assert panel.inner_spin.isVisibleTo(inspector)
    assert not panel.start_spin.isVisibleTo(inspector)

    panel.points_spin.setValue(9)
    panel.inner_spin.setValue(32)
    panel.parameter_rotation_spin.setValue(-72)
    panel._emit_properties()

    assert emitted[-1][0] == row["id"]
    assert emitted[-1][1]["content"]["point_count"] == 9
    assert emitted[-1][1]["content"]["inner_radius"] == 0.32
    assert emitted[-1][1]["content"]["rotation_offset"] == -72.0
    inspector.deleteLater()
    app.processEvents()
