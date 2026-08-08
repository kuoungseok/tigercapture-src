from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_overlay_resolves_right_bottom_constraints_after_artboard_resize() -> None:
    app = _app()
    from app.painter_ui_constraints import capture_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(400, 300)
    document, row = add_ui_object(
        document,
        kind="button",
        x=280,
        y=230,
        width=100,
        height=50,
    )
    row = document["objects"][0]
    row["constraints"] = capture_ui_constraints(
        row,
        {"x": 0, "y": 0, "width": 400, "height": 300},
        {"horizontal": "right", "vertical": "bottom"},
    )
    document["artboards"][0]["width"] = 600
    document["artboards"][0]["height"] = 500

    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    geometry = overlay._resolved_geometry[row["id"]]
    assert geometry["x"] == 480.0
    assert geometry["y"] == 430.0
    overlay.deleteLater()
    app.processEvents()


def test_overlay_uses_custom_pivot_for_rotation_handle_and_hit_transform() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, QRectF

    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    rect = QRectF(100, 80, 200, 100)
    constraints = {"pivot_x": 0.25, "pivot_y": 0.75}
    handle = overlay._rotation_handle_rect(rect, constraints)
    assert handle.center().x() == 150.0

    pivot = QPointF(150, 155)
    rotated = QPointF(150, 105)
    restored = overlay._unrotated_point(
        rotated,
        rect,
        90.0,
        constraints,
    )
    # Painter stores Figma inspector angles: +90 is counterclockwise.
    # The screen point above the pivot therefore maps back to the local point
    # on the right side of the pivot.
    assert abs(restored.x() - 200.0) < 0.001
    assert abs(restored.y() - pivot.y()) < 0.001
    overlay.deleteLater()
    app.processEvents()


def test_overlay_resize_applies_aspect_and_maximum_size() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, QRectF, Qt

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(800, 600)
    document, row = add_ui_object(
        document,
        kind="rectangle",
        x=100,
        y=100,
        width=200,
        height=100,
    )
    row = document["objects"][0]
    row["constraints"] = {
        "lock_aspect": True,
        "aspect_ratio": 2.0,
        "min_width": 120,
        "min_height": 60,
        "max_width": 240,
        "max_height": 120,
    }
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay._active_object_id = row["id"]
    overlay._active_handle = "se"
    overlay._original_rect = QRectF(overlay._object_rect(row))
    _viewport, scale = overlay._artboard_viewport()
    oversized_point = QPointF(
        overlay._original_rect.left() + 500 * scale,
        overlay._original_rect.top() + 300 * scale,
    )
    resized = overlay._resize_rect(
        oversized_point,
        Qt.KeyboardModifier.NoModifier,
    )
    assert abs(resized.width() / scale - 240.0) < 0.001
    assert abs(resized.height() / scale - 120.0) < 0.001
    assert resized.topLeft() == overlay._original_rect.topLeft()
    overlay.deleteLater()
    app.processEvents()
