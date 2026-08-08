from __future__ import annotations

import pytest


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


def test_custom_point_anchor_preserves_rect_and_tracks_parent_resize() -> None:
    from app.painter_ui_constraints import (
        capture_ui_constraints,
        resolve_ui_constraints,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, _row = add_ui_object(
        create_ui_document(400, 300),
        kind="button",
        x=100,
        y=60,
        width=80,
        height=40,
    )
    authored = document["objects"][0]
    authored["constraints"] = capture_ui_constraints(
        authored,
        {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0},
        {
            "horizontal": "custom",
            "vertical": "custom",
            "anchor_min_x": 0.25,
            "anchor_max_x": 0.25,
            "anchor_min_y": 0.5,
            "anchor_max_y": 0.5,
            "pivot_x": 0.25,
            "pivot_y": 0.75,
        },
    )
    constraints = authored["constraints"]
    assert constraints["anchor_offset_left"] == pytest.approx(20.0)
    assert constraints["anchor_offset_right"] == pytest.approx(80.0)
    assert constraints["anchor_offset_top"] == pytest.approx(-60.0)
    assert constraints["anchor_offset_bottom"] == pytest.approx(40.0)
    assert resolve_ui_constraints(document)[authored["id"]] == {
        "x": 100.0,
        "y": 60.0,
        "width": 80.0,
        "height": 40.0,
    }

    document["artboards"][0]["width"] = 800
    document["artboards"][0]["height"] = 600
    assert resolve_ui_constraints(document)[authored["id"]] == {
        "x": 200.0,
        "y": 210.0,
        "width": 80.0,
        "height": 40.0,
    }


def test_custom_stretched_anchor_preserves_margins_across_parent_resize() -> None:
    from app.painter_ui_constraints import (
        capture_ui_constraints,
        resolve_ui_constraints,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, _row = add_ui_object(
        create_ui_document(400, 300),
        kind="frame",
        x=100,
        y=60,
        width=200,
        height=100,
    )
    authored = document["objects"][0]
    authored["constraints"] = capture_ui_constraints(
        authored,
        {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0},
        {
            "horizontal": "custom",
            "vertical": "custom",
            "anchor_min_x": 0.2,
            "anchor_max_x": 0.8,
            "anchor_min_y": 0.1,
            "anchor_max_y": 0.9,
        },
    )
    constraints = authored["constraints"]
    assert constraints["anchor_offset_left"] == pytest.approx(20.0)
    assert constraints["anchor_offset_right"] == pytest.approx(20.0)
    assert constraints["anchor_offset_top"] == pytest.approx(30.0)
    assert constraints["anchor_offset_bottom"] == pytest.approx(110.0)

    document["artboards"][0]["width"] = 800
    document["artboards"][0]["height"] = 600
    assert resolve_ui_constraints(document)[authored["id"]] == {
        "x": 180.0,
        "y": 90.0,
        "width": pytest.approx(440.0),
        "height": pytest.approx(340.0),
    }


def test_custom_anchor_normalization_clamps_orders_and_collapses_noise() -> None:
    from app.painter_ui_constraints import normalize_ui_constraints

    constraints = normalize_ui_constraints(
        {
            "horizontal": "custom",
            "vertical": "custom",
            "anchor_min_x": 1.4,
            "anchor_max_x": -0.2,
            "anchor_min_y": 0.4,
            "anchor_max_y": 0.4000005,
        },
        width=80,
        height=40,
    )
    assert constraints["anchor_min_x"] == 0.0
    assert constraints["anchor_max_x"] == 1.0
    assert constraints["anchor_min_y"] == constraints["anchor_max_y"] == 0.4


def test_document_constraint_resolution_uses_parent_indexes(monkeypatch) -> None:
    """Bulk resolution must not fall back to one full scan per object."""
    import app.painter_ui_constraints as constraint_module
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, parent = add_ui_object(
        document,
        kind="frame",
        x=40,
        y=50,
        width=500,
        height=300,
    )
    child_ids: list[str] = []
    for index in range(64):
        document, child = add_ui_object(
            document,
            parent_id=parent["id"],
            x=60 + index,
            y=80,
            width=40,
            height=20,
        )
        child_ids.append(child["id"])

    def reject_linear_parent_scan(*_args, **_kwargs):
        raise AssertionError("bulk constraint resolution used the linear helper")

    monkeypatch.setattr(
        constraint_module,
        "constraint_parent_geometry",
        reject_linear_parent_scan,
    )
    geometry = constraint_module.resolve_ui_constraints(document)

    assert len(geometry) == 65
    assert geometry[child_ids[-1]]["x"] == 123.0
