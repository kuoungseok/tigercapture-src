from __future__ import annotations

import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_painter_actions_register_and_control_standalone_dialog(tmp_path: Path) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    required = {
        "paint.state",
        "paint.document.new",
        "paint.document.export_png",
        "paint.view.zoom",
        "paint.view.pan",
        "paint.tool.set",
        "paint.window.show_panel",
        "paint.layer.add",
        "paint.layer.select",
        "paint.layer.rename",
        "paint.layer.duplicate",
        "paint.layer.delete",
        "paint.layer.set_visible",
        "paint.layer.set_locked",
        "paint.layer.set_opacity",
        "paint.layer.set_blend_mode",
        "paint.channel.set_visible",
        "paint.selection.select_all",
        "paint.selection.deselect",
        "paint.selection.invert",
        "paint.selection.to_path",
        "paint.path.to_selection",
        "paint.path.create",
        "paint.path.delete",
        "paint.path.clear",
        "paint.path.commit",
        "paint.clipboard.copy",
        "paint.clipboard.cut",
        "paint.clipboard.paste",
    }
    assert required <= action_ids

    state = registry.execute("paint.state").to_dict()
    assert state["ok"]
    assert state["result"]["document"]["width"] == 640

    added = registry.execute("paint.layer.add", {"name": "AI Ink"}).to_dict()
    assert added["ok"]
    layer_id = added["result"]["active_layer_id"]
    assert any(row["name"] == "AI Ink" for row in added["result"]["layers"])

    selected_layer = registry.execute(
        "paint.layer.select",
        {"layer_id": layer_id},
    ).to_dict()
    assert selected_layer["ok"]
    assert selected_layer["result"]["active_layer_id"] == layer_id

    tool = registry.execute("paint.tool.set", {"tool": "path"}).to_dict()
    assert tool["ok"]
    assert dialog.path_btn.isChecked()

    panel = registry.execute("paint.window.show_panel", {"panel": "paths"}).to_dict()
    assert panel["ok"]
    assert dialog._layer_channel_path_tabs.currentIndex() == 2

    renamed = registry.execute(
        "paint.layer.rename",
        {"layer_id": layer_id, "name": "Line Art"},
    ).to_dict()
    assert renamed["ok"]
    assert any(row["name"] == "Line Art" for row in renamed["result"]["layers"])

    opacity = registry.execute(
        "paint.layer.set_opacity",
        {"layer_id": layer_id, "opacity": 42},
    ).to_dict()
    assert opacity["ok"]
    assert next(row for row in opacity["result"]["layers"] if row["layer_id"] == layer_id)["opacity"] == 42

    blend = registry.execute(
        "paint.layer.set_blend_mode",
        {"layer_id": layer_id, "blend_mode": "multiply"},
    ).to_dict()
    assert blend["ok"]
    assert next(row for row in blend["result"]["layers"] if row["layer_id"] == layer_id)["blend_mode"] == "multiply"

    hidden = registry.execute(
        "paint.layer.set_visible",
        {"layer_id": layer_id, "visible": False},
    ).to_dict()
    assert hidden["ok"]
    assert next(row for row in hidden["result"]["layers"] if row["layer_id"] == layer_id)["visible"] is False

    locked = registry.execute(
        "paint.layer.set_locked",
        {"layer_id": layer_id, "locked": True},
    ).to_dict()
    assert locked["ok"]
    assert next(row for row in locked["result"]["layers"] if row["layer_id"] == layer_id)["locked"] is True

    channel = registry.execute(
        "paint.channel.set_visible",
        {"channel": "Red", "visible": False},
    ).to_dict()
    assert channel["ok"]
    assert channel["result"]["channels"]["Red"] is False

    selected = registry.execute("paint.selection.select_all").to_dict()
    assert selected["ok"]
    assert selected["result"]["selection"]["active"] is True
    assert selected["result"]["selection"]["point_count"] == 4

    inverted = registry.execute("paint.selection.invert").to_dict()
    assert inverted["ok"]
    assert inverted["result"]["selection"]["inverted"] is True

    path = registry.execute("paint.selection.to_path").to_dict()
    assert path["ok"]
    assert path["result"]["paths"]["saved_path_count"] >= 1

    path_to_selection = registry.execute(
        "paint.path.to_selection",
        {"path_id": "path:0"},
    ).to_dict()
    assert path_to_selection["ok"]
    assert path_to_selection["result"]["selection"]["active"] is True

    created_path = registry.execute(
        "paint.path.create",
        {
            "points": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.9, "y": 0.1},
                {"x": 0.5, "y": 0.8},
            ],
            "closed": True,
        },
    ).to_dict()
    assert created_path["ok"]
    assert created_path["result"]["paths"]["saved_path_count"] >= 2

    deleted_path = registry.execute("paint.path.delete", {"path_id": "path:1"}).to_dict()
    assert deleted_path["ok"]

    zoom = registry.execute("paint.view.zoom", {"percent": 150}).to_dict()
    assert zoom["ok"]
    assert zoom["result"]["view"]["zoom_percent"] == 150

    pan = registry.execute("paint.view.pan", {"dx": 20, "dy": 10}).to_dict()
    assert pan["ok"]

    copied = registry.execute("paint.clipboard.copy").to_dict()
    assert copied["ok"]
    pasted = registry.execute("paint.clipboard.paste").to_dict()
    assert pasted["ok"]
    assert len(pasted["result"]["layers"]) >= 3

    out_path = tmp_path / "painter_action_overlay.png"
    exported = registry.execute(
        "paint.document.export_png",
        {"path": str(out_path), "include_background": False},
    ).to_dict()
    assert exported["ok"]
    assert out_path.exists()

    new_doc = registry.execute(
        "paint.document.new",
        {"width": 800, "height": 600, "background": "transparent"},
    ).to_dict()
    assert new_doc["ok"]
    assert new_doc["result"]["document"]["width"] == 800
    assert new_doc["result"]["document"]["background_layer_present"] is False

    from PySide6.QtWidgets import QApplication

    QApplication.clipboard().clear()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
