from __future__ import annotations


def test_constraint_capture_and_right_bottom_resolution() -> None:
    from app.painter_ui_constraints import (
        capture_ui_constraints,
        resolve_ui_constraints,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(400, 300, name="Phone")
    document, row = add_ui_object(
        document,
        kind="button",
        x=250,
        y=220,
        width=120,
        height=48,
    )
    parent = {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0}
    row["constraints"] = capture_ui_constraints(
        row,
        parent,
        {"horizontal": "right", "vertical": "bottom"},
    )
    document["objects"][0] = row
    document["artboards"][0]["width"] = 520
    document["artboards"][0]["height"] = 420

    geometry = resolve_ui_constraints(document)[row["id"]]
    assert geometry == {
        "x": 370.0,
        "y": 340.0,
        "width": 120.0,
        "height": 48.0,
    }


def test_stretch_and_scale_constraints_follow_parent_size() -> None:
    from app.painter_ui_constraints import (
        capture_ui_constraints,
        resolve_ui_constraints,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(400, 300, name="Desktop")
    document, stretch = add_ui_object(
        document,
        x=20,
        y=30,
        width=360,
        height=40,
    )
    document, scale = add_ui_object(
        document,
        x=100,
        y=100,
        width=80,
        height=60,
    )
    parent = {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0}
    document["objects"][0]["constraints"] = capture_ui_constraints(
        stretch,
        parent,
        {"horizontal": "stretch"},
    )
    document["objects"][1]["constraints"] = capture_ui_constraints(
        scale,
        parent,
        {"horizontal": "scale", "vertical": "scale"},
    )
    document["artboards"][0]["width"] = 800
    document["artboards"][0]["height"] = 600

    geometry = resolve_ui_constraints(document)
    assert geometry[stretch["id"]]["x"] == 20.0
    assert geometry[stretch["id"]]["width"] == 760.0
    assert geometry[scale["id"]] == {
        "x": 200.0,
        "y": 200.0,
        "width": 160.0,
        "height": 120.0,
    }


def test_size_limits_and_locked_aspect_are_applied_together() -> None:
    from app.painter_ui_constraints import constrain_ui_size

    constraints = {
        "min_width": 120,
        "min_height": 60,
        "max_width": 240,
        "max_height": 120,
        "lock_aspect": True,
        "aspect_ratio": 2.0,
    }
    assert constrain_ui_size(60, 20, constraints) == (120.0, 60.0)
    assert constrain_ui_size(400, 300, constraints) == (240.0, 120.0)
    assert constrain_ui_size(180, 70, constraints) == (180.0, 90.0)


def test_pivot_and_reanchored_resize_preserve_expected_anchor() -> None:
    from PySide6.QtCore import QRectF

    from app.painter_ui_constraints import reanchor_resize_rect, ui_pivot_point

    original = QRectF(10, 20, 100, 50)
    pivot = ui_pivot_point(original, {"pivot_x": 0.25, "pivot_y": 0.8})
    assert (pivot.x(), pivot.y()) == (35.0, 60.0)
    resized = reanchor_resize_rect(
        QRectF(),
        original,
        "nw",
        center_based=False,
        width=160,
        height=80,
    )
    assert resized == QRectF(-50, -10, 160, 80)
    centered = reanchor_resize_rect(
        QRectF(),
        original,
        "se",
        center_based=True,
        width=200,
        height=100,
    )
    assert centered == QRectF(-40, -5, 200, 100)
