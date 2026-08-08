from __future__ import annotations

import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _motion_composition():
    from app.motion_designer.schema import (
        Keyframe,
        MotionComposition,
        MotionLayer,
        SourceRef,
    )

    composition = MotionComposition(
        name="Painter Actor",
        width=640,
        height=360,
        duration_ms=1000,
        fps=30.0,
    )
    layer = MotionLayer(
        name="Moving Card",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": 180.0,
                "height": 90.0,
                "fill": "#38D6A4",
                "radius": 12.0,
            },
        ),
        out_ms=1000,
    )
    layer.transform.position.keyframes = [
        Keyframe(time_ms=0, value=[180.0, 180.0]),
        Keyframe(time_ms=999, value=[460.0, 180.0]),
    ]
    composition.layers.append(layer)
    return composition


def test_motion_actor_contract_places_and_renders_animation() -> None:
    _app()
    from PySide6.QtCore import QRectF

    from app.painter_ui_document import create_ui_document, validate_ui_document
    from app.painter_ui_motion_actor import (
        add_motion_actor,
        motion_actor_composition_id,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    composition = _motion_composition()
    document, actor = add_motion_actor(
        create_ui_document(1280, 720),
        composition,
        source_path="lesson.tgmotion",
    )
    assert validate_ui_document(document)["ok"]
    assert actor["kind"] == "motion_actor"
    assert motion_actor_composition_id(actor) == composition.id
    assert actor["width"] / actor["height"] == 640 / 360

    overlay = PainterUIDesignOverlay()
    overlay.set_document(document)
    overlay.set_motion_actor_sources({composition.id: composition})
    first = overlay._motion_actor_frame(actor, QRectF(0, 0, 640, 360))
    overlay.set_motion_actor_time(500)
    second = overlay._motion_actor_frame(actor, QRectF(0, 0, 640, 360))
    assert first is not None and not first.isNull()
    assert second is not None and not second.isNull()
    assert first != second
    overlay.deleteLater()


def test_motion_actor_action_import_persists_in_painter_document(
    tmp_path: Path,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.motion_designer.project_io import save_motion_project

    motion_path = save_motion_project(
        _motion_composition(),
        tmp_path / "actor.tgmotion",
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1280, 720, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    imported = registry.execute(
        "paint.ui.motion_actor.import",
        {
            "path": str(motion_path),
            "x": 100,
            "y": 80,
            "width": 640,
            "height": 360,
        },
    ).to_dict()
    assert imported["ok"]
    object_id = imported["result"]["object_id"]
    composition_id = imported["result"]["composition_id"]
    listed = registry.execute("paint.ui.motion_actor.list", {}).to_dict()
    assert listed["ok"]
    assert listed["result"]["count"] == 1
    assert listed["result"]["actors"][0]["object_id"] == object_id

    painter_path = tmp_path / "motion_actor.tspaint"
    dialog.save_document_to_path(painter_path)
    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(painter_path)
    restored_registry = ActionRegistry(owner=restored)
    restored_list = restored_registry.execute(
        "paint.ui.motion_actor.list",
        {},
    ).to_dict()
    assert restored_list["result"]["count"] == 1
    assert restored_list["result"]["actors"][0]["composition_available"]
    assert composition_id in restored._painter_ui_motion_compositions

    dialog.close()
    restored.close()
    dialog.deleteLater()
    restored.deleteLater()
    app.processEvents()
