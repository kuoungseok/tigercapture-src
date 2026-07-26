from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_painter_ui_actions_workspace_undo_and_native_round_trip(
    tmp_path: Path,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.ui.document.inspect",
        "paint.ui.workspace.set",
        "paint.ui.artboard.add",
        "paint.ui.artboard.update",
        "paint.ui.artboard.remove",
        "paint.ui.object.add",
        "paint.ui.object.update",
        "paint.ui.object.remove",
        "paint.ui.delivery.profiles",
        "paint.ui.delivery.preflight",
        "paint.ui.handoff.export",
    } <= action_ids

    workspace = registry.execute(
        "paint.ui.workspace.set",
        {"mode": "ui_design"},
    ).to_dict()
    assert workspace["ok"]
    assert workspace["result"]["workspace"]["mode"] == "ui_design"
    assert dialog._canvas_mode_ui_btn.isChecked()
    assert dialog._painter_ui_overlay.isVisible()

    added = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "button",
            "name": "Continue",
            "x": 48,
            "y": 700,
            "width": 294,
            "height": 56,
            "style": {"fill": "#4267E8"},
            "content": {"text": "Continue"},
        },
    ).to_dict()
    assert added["ok"]
    state = added["result"]
    assert state["ui_design"]["validation"]["object_count"] == 1
    object_id = state["ui_design"]["selected_object_id"]
    assert object_id

    updated = registry.execute(
        "paint.ui.object.update",
        {"object_id": object_id, "changes": {"width": 300, "x": 45}},
    ).to_dict()
    assert updated["ok"]
    obj = updated["result"]["ui_design"]["document"]["objects"][0]
    assert obj["width"] == 300.0
    assert obj["x"] == 45.0

    dialog._undo()
    undone = dialog.painter_action_state()
    obj = undone["ui_design"]["document"]["objects"][0]
    assert obj["width"] == 294.0
    dialog._redo()
    redone = dialog.painter_action_state()
    assert redone["ui_design"]["document"]["objects"][0]["width"] == 300.0

    handoff_dir = tmp_path / "handoff"
    handoff = registry.execute(
        "paint.ui.handoff.export",
        {"output_dir": str(handoff_dir)},
    ).to_dict()
    assert handoff["ok"]
    assert (handoff_dir / "manifest.json").exists()

    document_path = tmp_path / "ui_design.tspaint"
    saved = registry.execute(
        "paint.document.save",
        {"path": str(document_path)},
    ).to_dict()
    assert saved["ok"]
    with zipfile.ZipFile(document_path, "r") as archive:
        stored = json.loads(archive.read("document.json"))
    assert stored["ui_document"]["schema"] == "tigerstudio.painter.ui.v1"
    assert stored["ui_document"]["objects"][0]["name"] == "Continue"
    assert stored["workspace"]["mode"] == "ui_design"

    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(document_path)
    restored_state = restored.painter_action_state()
    assert restored_state["workspace"]["mode"] == "ui_design"
    assert restored_state["ui_design"]["validation"]["object_count"] == 1
    assert (
        restored_state["ui_design"]["document"]["objects"][0]["content"]["text"]
        == "Continue"
    )

    dialog.close()
    restored.close()
    dialog.deleteLater()
    restored.deleteLater()
    app.processEvents()


def test_painter_ui_design_toolbar_adds_and_moves_visible_objects() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    dialog._set_canvas_workspace_mode("ui_design")
    app.processEvents()
    assert dialog._ui_design_tool_host.isVisible()
    dialog._ui_design_tool_buttons["frame"].click()
    dialog._ui_design_tool_buttons["text"].click()
    app.processEvents()
    state = dialog.painter_action_state()
    assert state["ui_design"]["validation"]["object_count"] == 2
    assert dialog._painter_ui_overlay.isVisible()

    object_id = state["ui_design"]["selected_object_id"]
    original = next(
        row
        for row in state["ui_design"]["document"]["objects"]
        if row["id"] == object_id
    )
    dialog._move_painter_ui_object(
        object_id,
        float(original["x"]) + 40.0,
        float(original["y"]) + 30.0,
    )
    moved = dialog.painter_action_state()["ui_design"]["document"]["objects"]
    moved_row = next(row for row in moved if row["id"] == object_id)
    assert moved_row["x"] == original["x"] + 40.0
    assert moved_row["y"] == original["y"] + 30.0
    dialog._undo()
    restored = dialog.painter_action_state()["ui_design"]["document"]["objects"]
    restored_row = next(row for row in restored if row["id"] == object_id)
    assert restored_row["x"] == original["x"]
    assert restored_row["y"] == original["y"]

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
