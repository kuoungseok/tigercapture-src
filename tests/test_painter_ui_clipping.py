from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _clipping_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(400, 300, name="Clip")
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Viewport",
        x=80,
        y=70,
        width=120,
        height=100,
        style={"fill": "#00000000", "stroke": "#00000000", "radius": 10},
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        name="Overflow",
        parent_id=frame["id"],
        x=140,
        y=95,
        width=120,
        height=50,
        style={"fill": "#FF2020FF", "stroke": "#FF2020FF"},
    )
    return document, frame, child


def test_frame_clip_service_persists_and_rejects_non_frame() -> None:
    from app.painter_ui_clipping import inspect_ui_clip, set_ui_clip
    from app.painter_ui_document import PainterUIDocumentError

    document, frame, child = _clipping_document()
    document, updated = set_ui_clip(document, frame["id"], True)
    assert updated["clip_content"] is True
    report = inspect_ui_clip(document, frame["id"])
    assert report["supported"] is True
    assert report["clip_content"] is True
    assert report["child_ids"] == [child["id"]]
    with pytest.raises(PainterUIDocumentError):
        set_ui_clip(document, child["id"], True)


def test_canvas_clips_overflow_pixels_and_hit_target_to_parent_frame() -> None:
    app = _app()
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage

    from app.painter_ui_clipping import set_ui_clip
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, frame, child = _clipping_document()
    document, _ = set_ui_clip(document, frame["id"], True)
    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 520)
    overlay.set_document(document)
    parent_rect = overlay._object_rect(frame)
    child_rect = overlay._object_rect(child)
    inside = QPointF(
        min(parent_rect.right() - 8.0, child_rect.left() + 8.0),
        child_rect.center().y(),
    )
    overflow = QPointF(
        min(child_rect.right() - 8.0, parent_rect.right() + 20.0),
        child_rect.center().y(),
    )
    assert overlay._point_visible_in_parent_clips(child, inside)
    assert not overlay._point_visible_in_parent_clips(child, overflow)

    image = QImage(
        overlay.size(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(0)
    overlay.render(image)
    inside_color = image.pixelColor(inside.toPoint())
    overflow_color = image.pixelColor(overflow.toPoint())
    assert inside_color.red() > inside_color.blue() + 100
    assert overflow_color.red() == overflow_color.blue()
    overlay.deleteLater()
    app.processEvents()


def test_clip_inspector_and_actions_use_the_same_contract() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import select_ui_object

    document, frame, _child = _clipping_document()
    document = select_ui_object(document, frame["id"])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(400, 300, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    dialog._paint_ui_inspector.set_document(document)
    assert dialog._paint_ui_inspector.clip_content_check.isEnabled()

    registry = ActionRegistry(owner=dialog)
    action_ids = {item["id"] for item in registry.list_actions()}
    assert {"paint.ui.clip.inspect", "paint.ui.clip.set"} <= action_ids
    result = registry.execute(
        "paint.ui.clip.set",
        {"object_id": frame["id"], "clip_content": True},
    ).to_dict()
    assert result["ok"]
    inspected = registry.execute(
        "paint.ui.clip.inspect",
        {"object_id": frame["id"]},
    ).to_dict()
    assert inspected["ok"]
    assert inspected["result"]["clip_content"] is True
    dialog.close()
    app.processEvents()
