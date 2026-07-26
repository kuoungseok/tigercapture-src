from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_responsive_overrides_normalize_and_resolve_by_specificity() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        normalize_ui_document,
    )
    from app.painter_ui_responsive import resolve_ui_responsive_document

    document = create_ui_document(390, 844)
    document["artboards"][0]["breakpoint"] = "mobile"
    document, row = add_ui_object(
        document,
        kind="button",
        x=20,
        y=40,
        width=200,
        height=48,
    )
    document["objects"][0]["responsive_overrides"] = [
        {
            "breakpoint": "any",
            "orientation": "portrait",
            "changes": {"x": 30, "style": {"radius": 12}},
        },
        {
            "id": "button-mobile-portrait",
            "breakpoint": "mobile",
            "orientation": "portrait",
            "changes": {"x": 44, "width": 280, "visible": False},
        },
    ]
    normalized = normalize_ui_document(document)
    overrides = normalized["objects"][0]["responsive_overrides"]
    assert overrides[0]["id"] == f"{row['id']}-responsive-1"
    assert overrides[1]["id"] == "button-mobile-portrait"

    resolved = resolve_ui_responsive_document(normalized)["objects"][0]
    assert resolved["x"] == 44.0
    assert resolved["width"] == 280.0
    assert resolved["visible"] is False
    assert resolved["style"]["radius"] == 12
    assert "responsive_override_id" in resolved


def test_responsive_geometry_flows_into_canvas_resolution() -> None:
    _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(390, 844)
    document["artboards"][0]["breakpoint"] = "mobile"
    document, row = add_ui_object(
        document,
        kind="rectangle",
        x=10,
        y=20,
        width=100,
        height=40,
    )
    document["objects"][0]["responsive_overrides"] = [
        {
            "breakpoint": "mobile",
            "orientation": "portrait",
            "changes": {"x": 80, "y": 90, "width": 220},
        }
    ]
    overlay = PainterUIDesignOverlay()
    overlay.resize(600, 700)
    overlay.set_document(document)
    assert overlay._effective_document["objects"][0]["x"] == 80.0
    assert overlay._resolved_geometry[row["id"]]["width"] == 220.0
    overlay.deleteLater()


def test_responsive_actions_set_remove_and_undo_override() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._add_default_painter_ui_object("button")
    object_id = dialog._painter_ui_document["objects"][-1]["id"]
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.responsive.override.set",
        {
            "object_id": object_id,
            "breakpoint": "mobile",
            "orientation": "portrait",
            "changes": {"x": 72, "width": 260, "opacity": 0.8},
        },
    ).to_dict()
    assert result["ok"] is True
    override = result["result"]["ui_design"]["document"]["objects"][-1][
        "responsive_overrides"
    ][0]
    assert override["changes"]["x"] == 72.0
    assert override["changes"]["width"] == 260.0

    removed = registry.execute(
        "paint.ui.responsive.override.remove",
        {
            "object_id": object_id,
            "breakpoint": "mobile",
            "orientation": "portrait",
        },
    ).to_dict()
    assert removed["ok"] is True
    assert (
        removed["result"]["ui_design"]["document"]["objects"][-1][
            "responsive_overrides"
        ]
        == []
    )
    dialog._undo()
    assert dialog._painter_ui_document["objects"][-1]["responsive_overrides"]
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_inspector_routes_geometry_to_current_responsive_context() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(390, 844)
    document["artboards"][0]["breakpoint"] = "mobile"
    document, row = add_ui_object(document, kind="button", width=200, height=48)
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[tuple[str, str, str, dict]] = []
    inspector.responsive_override_changed.connect(
        lambda object_id, breakpoint, orientation, changes: emitted.append(
            (object_id, breakpoint, orientation, changes)
        )
    )
    inspector.responsive_edit_check.setChecked(True)
    inspector.geometry_controls["x"].setValue(64)
    inspector.geometry_controls["width"].setValue(280)
    inspector._emit_geometry()

    assert emitted[-1][0:3] == (row["id"], "mobile", "portrait")
    assert emitted[-1][3]["x"] == 64.0
    assert emitted[-1][3]["width"] == 280.0
    assert inspector.responsive_status_label.text().endswith("No override")
    inspector.deleteLater()
    app.processEvents()
