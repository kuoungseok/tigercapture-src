from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _overlap_document(*, reverse_z_index: bool):
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document, parent = add_ui_object(
        create_ui_document(200, 120, name="Reverse Z"),
        kind="frame",
        name="Overlap Stack",
        x=20,
        y=20,
        width=150,
        height=60,
        style={"fill": "#00000000", "stroke_width": 0},
    )
    document, _parent = update_ui_object(
        document,
        parent["id"],
        {
            "layout": {
                "mode": "horizontal",
                "gap": -50,
                "cross_gap": 0,
                "width_sizing": "fixed",
                "height_sizing": "fixed",
                "main_alignment": "start",
                "cross_alignment": "start",
                "reverse_z_index": reverse_z_index,
            }
        },
    )
    document, first = add_ui_object(
        document,
        kind="rectangle",
        name="First Red",
        parent_id=parent["id"],
        x=20,
        y=20,
        width=100,
        height=60,
        style={"fill": "#FF0000FF", "stroke_width": 0},
    )
    document, last = add_ui_object(
        document,
        kind="rectangle",
        name="Last Green",
        parent_id=parent["id"],
        x=70,
        y=20,
        width=100,
        height=60,
        style={"fill": "#00FF00FF", "stroke_width": 0},
    )
    document["selection"] = {"object_id": "", "object_ids": []}
    return document, parent, first, last


def test_reverse_z_reorders_direct_child_subtree_blocks_only() -> None:
    from app.painter_ui_paint_order import apply_ui_reverse_z_paint_order

    rows = [
        {
            "id": "parent",
            "parent_id": "",
            "layout": {"mode": "horizontal", "reverse_z_index": True},
        },
        {"id": "first", "parent_id": "parent", "layout": {}},
        {"id": "first-child", "parent_id": "first", "layout": {}},
        {"id": "unrelated", "parent_id": "", "layout": {}},
        {"id": "last", "parent_id": "parent", "layout": {}},
        {"id": "last-child", "parent_id": "last", "layout": {}},
    ]

    ordered = apply_ui_reverse_z_paint_order(rows)

    assert [row["id"] for row in ordered] == [
        "parent",
        "last",
        "last-child",
        "unrelated",
        "first",
        "first-child",
    ]
    assert ordered[1:3] == [rows[4], rows[5]]
    assert ordered[4:6] == [rows[1], rows[2]]


def test_negative_gap_reverse_z_changes_workspace_stack_not_geometry() -> None:
    _app()
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_workspace import PainterUIDesignOverlay

    normal, _parent, normal_first, normal_last = _overlap_document(
        reverse_z_index=False
    )
    reversed_document, _parent, reversed_first, reversed_last = (
        _overlap_document(reverse_z_index=True)
    )
    normal_geometry = resolve_ui_constraints(normal)
    reversed_geometry = resolve_ui_constraints(reversed_document)
    assert normal_geometry[normal_first["id"]] == reversed_geometry[
        reversed_first["id"]
    ]
    assert normal_geometry[normal_last["id"]] == reversed_geometry[
        reversed_last["id"]
    ]

    def overlap_color(document):
        overlay = PainterUIDesignOverlay()
        overlay.resize(400, 240)
        overlay.set_document(document)
        overlay.set_artboard_labels_visible(False)
        overlay.fit_artboard(document["active_artboard_id"])
        viewport, scale = overlay._artboard_viewport()
        image = QImage(
            overlay.width(),
            overlay.height(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(0)
        painter = QPainter(image)
        overlay.render(painter, QPoint(0, 0))
        painter.end()
        return image.pixelColor(
            int(round(viewport.left() + 85 * scale)),
            int(round(viewport.top() + 45 * scale)),
        )

    normal_color = overlap_color(normal)
    reversed_color = overlap_color(reversed_document)
    assert normal_color.green() > 240 and normal_color.red() < 20
    assert reversed_color.red() > 240 and reversed_color.green() < 20


def test_negative_gap_reverse_z_changes_asset_stack_not_geometry() -> None:
    _app()
    from app.painter_ui_asset_export import render_ui_artboard
    from app.painter_ui_constraints import resolve_ui_constraints

    normal, _parent, normal_first, normal_last = _overlap_document(
        reverse_z_index=False
    )
    reversed_document, _parent, reversed_first, reversed_last = (
        _overlap_document(reverse_z_index=True)
    )
    assert resolve_ui_constraints(normal)[normal_first["id"]] == (
        resolve_ui_constraints(reversed_document)[reversed_first["id"]]
    )
    assert resolve_ui_constraints(normal)[normal_last["id"]] == (
        resolve_ui_constraints(reversed_document)[reversed_last["id"]]
    )

    normal_image = render_ui_artboard(normal, normal["active_artboard_id"])
    reversed_image = render_ui_artboard(
        reversed_document,
        reversed_document["active_artboard_id"],
    )
    normal_color = normal_image.pixelColor(85, 45)
    reversed_color = reversed_image.pixelColor(85, 45)
    assert normal_color.green() > 240 and normal_color.red() < 20
    assert reversed_color.red() > 240 and reversed_color.green() < 20
