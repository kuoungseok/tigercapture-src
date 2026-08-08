from __future__ import annotations

import os
from pathlib import Path

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _source(path: Path, width: int = 400, height: int = 200) -> Path:
    _app()
    from PySide6.QtGui import QColor, QImage

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#2F82D0"))
    assert image.save(str(path), "PNG")
    return path


def test_place_image_preserves_aspect_and_selects_stable_object(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_image_assets import place_ui_image

    source = _source(tmp_path / "hero.png", 400, 200)
    document = create_ui_document(320, 240, name="Card")
    updated, row, report = place_ui_image(document, source)

    assert row["kind"] == "image"
    assert row["id"] == updated["selection"]["object_id"]
    assert row["width"] == pytest.approx(230.4)
    assert row["height"] == pytest.approx(115.2)
    assert row["content"]["source_path"] == str(source.resolve())
    assert row["content"]["original_width"] == 400
    assert row["content"]["original_height"] == 200
    assert report["source_size"] == [400, 200]
    assert report["object_id"] == row["id"]


def test_image_fill_preserves_identity_and_supports_focal_restore(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_image_assets import set_ui_image_fill

    source = _source(tmp_path / "portrait.png", 120, 180)
    document = create_ui_document(500, 500)
    document, rectangle = add_ui_object(
        document,
        kind="rectangle",
        name="Portrait Mask",
        width=240,
        height=240,
    )
    updated, row, report = set_ui_image_fill(
        document,
        rectangle["id"],
        source,
        image_fit="fill",
        focal_x=0.25,
        focal_y=0.8,
        restore_original_size=True,
    )

    assert row["id"] == rectangle["id"]
    assert row["kind"] == "rectangle"
    assert row["width"] == 120.0
    assert row["height"] == 180.0
    assert row["content"]["focal_x"] == 0.25
    assert row["content"]["focal_y"] == 0.8
    assert updated["selection"]["object_id"] == rectangle["id"]
    assert report["restored_original_size"] is True


def test_image_fill_rejects_missing_and_unsupported_targets(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        add_ui_object,
        create_ui_document,
    )
    from app.painter_ui_image_assets import (
        inspect_ui_image_source,
        set_ui_image_fill,
    )

    document = create_ui_document(320, 240)
    document, text = add_ui_object(document, kind="text")
    source = _source(tmp_path / "fill.png")
    with pytest.raises(PainterUIDocumentError, match="does not support"):
        set_ui_image_fill(document, text["id"], source)
    with pytest.raises(PainterUIDocumentError, match="does not exist"):
        inspect_ui_image_source(tmp_path / "missing.png")
    bad = tmp_path / "source.gif"
    bad.write_bytes(b"GIF89a")
    with pytest.raises(PainterUIDocumentError, match="Unsupported"):
        inspect_ui_image_source(bad)


def test_fill_plan_uses_normalized_focal_point() -> None:
    from PySide6.QtCore import QRectF, QSizeF

    from app.painter_ui_image_renderer import image_draw_plan

    left = image_draw_plan(
        QSizeF(200, 100),
        QRectF(0, 0, 100, 100),
        {"image_fit": "fill", "focal_x": 0.0},
    )
    right = image_draw_plan(
        QSizeF(200, 100),
        QRectF(0, 0, 100, 100),
        {"image_fit": "fill", "focal_x": 1.0},
    )
    assert left[0][1] == QRectF(0, 0, 100, 100)
    assert right[0][1] == QRectF(100, 0, 100, 100)


def test_image_actions_and_ui_wrapper_share_one_step_undo(
    tmp_path: Path,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    first = _source(tmp_path / "first.png", 200, 100)
    second = _source(tmp_path / "second.png", 80, 160)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {"paint.ui.image.place", "paint.ui.image.fill.set"} <= action_ids

    undo_count = len(dialog._undo_stack)
    placed = registry.execute(
        "paint.ui.image.place",
        {
            "source_path": str(first),
            "x": 24,
            "y": 32,
        },
    )
    assert placed.ok
    assert len(dialog._undo_stack) == undo_count + 1
    object_id = placed.result["image_place"]["object_id"]
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == object_id
    )["x"] == 24.0

    undo_count = len(dialog._undo_stack)
    filled = dialog._set_painter_ui_image_fill_path(
        object_id,
        str(second),
        restore_original_size=True,
    )
    assert len(dialog._undo_stack) == undo_count + 1
    assert filled["object_id"] == object_id
    row = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == object_id
    )
    assert row["width"] == 80.0
    assert row["height"] == 160.0

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_workspace_maps_drop_point_to_artboard_local_coordinates() -> None:
    app = _app()
    from PySide6.QtCore import QPointF

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(320, 240)
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.fit_artboard()
    artboard = document["artboards"][0]
    viewport, scale = overlay._artboard_viewport(artboard)
    mapped = overlay.artboard_point_at(viewport.center())

    assert mapped is not None
    assert mapped[0] == artboard["id"]
    assert mapped[1].x() == pytest.approx(160.0)
    assert mapped[1].y() == pytest.approx(120.0)
    assert overlay.artboard_point_at(QPointF(-20, -20)) is None

    overlay.deleteLater()
    app.processEvents()


def test_shape_image_fill_is_clipped_in_workspace_and_export(
    tmp_path: Path,
) -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_asset_export import render_ui_artboard
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_image_assets import set_ui_image_fill
    from app.painter_ui_workspace import PainterUIDesignOverlay

    source = _source(tmp_path / "ellipse-fill.png", 40, 40)
    document = create_ui_document(100, 100)
    document, ellipse = add_ui_object(
        document,
        kind="ellipse",
        x=10,
        y=10,
        width=80,
        height=80,
        style={"fill": "#202A37", "stroke": "#00000000", "stroke_width": 0},
    )
    document, ellipse, _report = set_ui_image_fill(
        document,
        ellipse["id"],
        source,
        image_fit="stretch",
    )

    overlay = PainterUIDesignOverlay()
    overlay.resize(240, 240)
    overlay.set_document(document)
    workspace = QImage(240, 240, QImage.Format.Format_ARGB32)
    workspace.fill(QColor("#101010"))
    painter = QPainter(workspace)
    overlay._paint_object(painter, ellipse)
    painter.end()
    rect = overlay._object_rect(ellipse)
    assert workspace.pixelColor(rect.center().toPoint()).name() == "#2f82d0"
    assert workspace.pixelColor(rect.topLeft().toPoint()).name() == "#101010"

    exported = render_ui_artboard(
        document,
        document["active_artboard_id"],
    )
    assert exported.pixelColor(50, 50).name() == "#2f82d0"
    assert exported.pixelColor(10, 10).name() == "#ffffff"
    overlay.deleteLater()
    app.processEvents()


def test_image_fill_inspector_is_contextual_and_restores_source_size() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(320, 240)
    document, rectangle = add_ui_object(
        document,
        kind="rectangle",
        width=200,
        height=120,
        content={
            "source_path": "embedded-image.png",
            "image_fit": "fill",
            "focal_x": 0.2,
            "focal_y": 0.8,
            "original_width": 640,
            "original_height": 360,
        },
    )
    inspector = PainterUIInspector()
    inspector.set_document(document)
    assert inspector.design_group_visible("image")
    assert inspector.image_focal_x_spin.isEnabled()
    assert inspector.image_focal_y_spin.isEnabled()
    assert inspector.image_focal_x_spin.value() == pytest.approx(0.2)
    assert inspector.image_focal_y_spin.value() == pytest.approx(0.8)
    assert inspector.image_original_size_button.isEnabled()

    emitted: list[tuple[str, dict]] = []
    inspector.properties_changed.connect(
        lambda object_id, changes: emitted.append((object_id, changes))
    )
    inspector.image_original_size_button.click()
    assert emitted[-1] == (
        rectangle["id"],
        {"width": 640.0, "height": 360.0},
    )
    inspector.deleteLater()
    app.processEvents()
