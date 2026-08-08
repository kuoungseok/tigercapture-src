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
        "paint.ui.responsive.preview_matrix.inspect",
        "paint.ui.template.catalog.inspect",
        "paint.ui.template.apply",
        "paint.ui.workspace.set",
        "paint.ui.view.fit",
        "paint.ui.view.focus",
        "paint.ui.view.zoom",
        "paint.ui.view.pan",
        "paint.ui.quick_action.search",
        "paint.ui.layout.diagnostics",
        "paint.ui.layout.stress_preview",
        "paint.ui.responsive.override.set",
        "paint.ui.responsive.override.remove",
        "paint.ui.theme.set",
        "paint.ui.theme.inspect",
        "paint.ui.token.theme.set",
        "paint.ui.token.theme.remove",
        "paint.ui.page.add",
        "paint.ui.page.update",
        "paint.ui.page.activate",
        "paint.ui.page.remove",
        "paint.ui.artboard.add",
        "paint.ui.artboard.activate",
        "paint.ui.artboard.update",
        "paint.ui.artboard.layout.set",
        "paint.ui.artboard.remove",
        "paint.ui.guide.create",
        "paint.ui.guide.update",
        "paint.ui.guide.remove",
        "paint.ui.guide.clear",
        "paint.ui.guide.visibility.set",
        "paint.ui.guide.lock.set",
        "paint.ui.ruler.visibility.set",
        "paint.ui.ruler.origin.set",
        "paint.ui.ruler.origin.reset",
        "paint.ui.object.add",
        "paint.ui.object.duplicate_to_artboard",
        "paint.ui.object.update",
        "paint.ui.object.properties.copy",
        "paint.ui.object.properties.paste",
        "paint.ui.object.paste_replace",
        "paint.ui.object.paste_in_place",
        "paint.ui.object.scale",
        "paint.ui.vector.node.add",
        "paint.ui.vector.node.update",
        "paint.ui.vector.node.remove",
        "paint.ui.vector.segment.set",
        "paint.ui.vector.segment.split",
        "paint.ui.vector.path.closed.set",
        "paint.ui.vector.path.join",
        "paint.ui.vector.path.reverse",
        "paint.ui.vector.path.simplify",
        "paint.ui.vector.path.outline",
        "paint.ui.text.content.set",
        "paint.ui.property.batch_set",
        "paint.ui.object.remove",
        "paint.ui.selection.set",
        "paint.ui.selection.parent",
        "paint.ui.selection.deep_select",
        "paint.ui.selection.scope.inspect",
        "paint.ui.selection.scope.enter",
        "paint.ui.selection.scope.exit",
        "paint.ui.object.arrange",
        "paint.ui.selection.tidy",
        "paint.ui.object.group",
        "paint.ui.object.ungroup",
        "paint.ui.object.reorder",
        "paint.ui.object.reparent",
        "paint.ui.component.add",
        "paint.ui.component.create",
        "paint.ui.component.instantiate",
            "paint.ui.component.sync",
            "paint.ui.component.property.define",
            "paint.ui.component.property.bind",
            "paint.ui.component.slot.define",
            "paint.ui.component.slot.inspect",
            "paint.ui.component.slot.insert",
            "paint.ui.component.slot.reset",
        "paint.ui.component.state.override.set",
        "paint.ui.component.instance.property.set",
        "paint.ui.component.variant.create",
        "paint.ui.component.variants.combine",
        "paint.ui.component.instance.variant.set",
        "paint.ui.component.instance.detach",
        "paint.ui.component.override.reset",
        "paint.ui.component.override.reset_all",
        "paint.ui.component.library.inspect",
        "paint.ui.component.playground.inspect",
        "paint.ui.token.library.inspect",
        "paint.ui.token.library.import",
        "paint.ui.token.library.export",
        "paint.ui.component.update",
        "paint.ui.component.remove",
        "paint.ui.token.add",
        "paint.ui.token.update",
        "paint.ui.token.remove",
            "paint.ui.token.bind",
            "paint.ui.token.unbind",
            "paint.ui.variable.collection.inspect",
            "paint.ui.variable.collection.add",
            "paint.ui.variable.collection.update",
            "paint.ui.variable.collection.remove",
            "paint.ui.variable.mode.add",
            "paint.ui.variable.mode.update",
            "paint.ui.variable.mode.remove",
            "paint.ui.variable.mode.set",
            "paint.ui.interaction.add",
        "paint.ui.interaction.update",
        "paint.ui.interaction.remove",
        "paint.ui.motion.attach",
        "paint.ui.motion.open",
        "paint.ui.motion.preview",
        "paint.ui.motion.inspect",
        "paint.ui.motion.delivery.inspect",
        "paint.ui.motion.binding.inspect",
        "paint.ui.motion.binding.migrate",
        "paint.ui.motion.binding.relink",
        "paint.ui.motion.binding.detach",
        "paint.ui.motion_actor.import",
        "paint.ui.motion_actor.list",
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

    artboard_added = registry.execute(
        "paint.ui.artboard.add",
        {"name": "Desktop", "width": 1440, "height": 900},
    ).to_dict()
    assert artboard_added["ok"]
    desktop_id = artboard_added["result"]["ui_design"]["active_artboard_id"]
    assert desktop_id != "artboard-1"
    artboards = artboard_added["result"]["ui_design"]["document"]["artboards"]
    assert artboards[1]["x"] > artboards[0]["x"] + artboards[0]["width"]
    activated = registry.execute(
        "paint.ui.artboard.activate",
        {"artboard_id": "artboard-1"},
    ).to_dict()
    assert activated["ok"]
    assert activated["result"]["ui_design"]["active_artboard_id"] == "artboard-1"

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

    selected = registry.execute(
        "paint.ui.selection.set",
        {"object_ids": [object_id], "primary_object_id": object_id},
    ).to_dict()
    assert selected["ok"]
    assert selected["result"]["ui_design"]["selected_object_ids"] == [object_id]
    arranged = registry.execute(
        "paint.ui.object.arrange",
        {"command": "right"},
    ).to_dict()
    assert arranged["ok"]
    assert (
        arranged["result"]["ui_design"]["document"]["objects"][0]["x"]
        == 90.0
    )
    fit_selection = registry.execute(
        "paint.ui.view.fit",
        {"mode": "selection"},
    ).to_dict()
    assert fit_selection["ok"]
    assert fit_selection["result"]["ui_view"]["mode"] == "selection"
    assert fit_selection["result"]["ui_view"]["zoom_percent"] > 0
    focused = registry.execute(
        "paint.ui.view.focus",
        {"object_id": object_id},
    ).to_dict()
    assert focused["ok"]
    assert focused["result"]["ui_view"]["mode"] == "object"
    zoomed = registry.execute(
        "paint.ui.view.zoom",
        {"percent": 175, "anchor_x": 200, "anchor_y": 180},
    ).to_dict()
    assert zoomed["ok"]
    assert zoomed["result"]["ui_view"]["zoom_percent"] == 175.0
    before_pan = zoomed["result"]["ui_view"]
    panned = registry.execute(
        "paint.ui.view.pan",
        {"dx": 24, "dy": -18},
    ).to_dict()
    assert panned["ok"]
    assert (
        panned["result"]["ui_view"]["offset_x"]
        == before_pan["offset_x"] + 24
    )
    assert (
        panned["result"]["ui_view"]["offset_y"]
        == before_pan["offset_y"] - 18
    )
    phone_view = dict(panned["result"]["ui_view"])
    switched_desktop = registry.execute(
        "paint.ui.artboard.activate",
        {"artboard_id": desktop_id},
    ).to_dict()
    assert switched_desktop["ok"]
    desktop_zoom = registry.execute(
        "paint.ui.view.zoom",
        {"percent": 82},
    ).to_dict()
    assert desktop_zoom["ok"]
    desktop_pan = registry.execute(
        "paint.ui.view.pan",
        {"dx": -31, "dy": 27},
    ).to_dict()
    assert desktop_pan["ok"]
    desktop_view = dict(desktop_pan["result"]["ui_view"])
    restored_phone = registry.execute(
        "paint.ui.artboard.activate",
        {"artboard_id": "artboard-1"},
    ).to_dict()
    assert restored_phone["ok"]
    phone_after_switch = dialog._painter_ui_overlay.view_state()
    assert phone_after_switch["zoom_percent"] == phone_view["zoom_percent"]
    assert abs(
        phone_after_switch["center_x"] - phone_view["center_x"]
    ) < 0.001
    assert abs(
        phone_after_switch["center_y"] - phone_view["center_y"]
    ) < 0.001
    registry.execute(
        "paint.ui.artboard.activate",
        {"artboard_id": desktop_id},
    )
    desktop_after_switch = dialog._painter_ui_overlay.view_state()
    assert desktop_after_switch["zoom_percent"] == desktop_view["zoom_percent"]
    assert abs(
        desktop_after_switch["center_x"] - desktop_view["center_x"]
    ) < 0.001
    assert abs(
        desktop_after_switch["center_y"] - desktop_view["center_y"]
    ) < 0.001
    registry.execute(
        "paint.ui.artboard.activate",
        {"artboard_id": "artboard-1"},
    )
    component_result = registry.execute(
        "paint.ui.component.add",
        {"name": "Primary Button", "root_object_id": object_id},
    ).to_dict()
    assert component_result["ok"]
    component_id = component_result["result"]["ui_design"]["document"][
        "components"
    ][0]["id"]
    token_result = registry.execute(
        "paint.ui.token.add",
        {"name": "Brand Primary", "kind": "color", "value": "#4267E8"},
    ).to_dict()
    assert token_result["ok"]
    token_id = token_result["result"]["ui_design"]["document"]["tokens"][0]["id"]
    bound = registry.execute(
        "paint.ui.object.update",
        {
            "object_id": object_id,
            "changes": {
                "component_id": component_id,
                "token_bindings": {"style.fill": token_id},
            },
        },
    ).to_dict()
    assert bound["ok"]
    interaction_result = registry.execute(
        "paint.ui.interaction.add",
        {
            "name": "Continue",
            "source_object_id": object_id,
            "trigger": "click",
            "action": "change_state",
            "target_object_id": object_id,
            "component_id": component_id,
            "parameters": {"state": "pressed"},
        },
    ).to_dict()
    assert interaction_result["ok"]

    motion_result = registry.execute(
        "paint.ui.motion.attach",
        {"object_id": object_id, "duration_ms": 800},
    ).to_dict()
    assert motion_result["ok"]
    composition_id = motion_result["result"]["composition_id"]
    assert motion_result["result"]["composition"]["duration_ms"] == 800
    inspected_motion = registry.execute(
        "paint.ui.motion.inspect",
        {"object_id": object_id},
    ).to_dict()
    assert inspected_motion["ok"]
    assert inspected_motion["result"]["composition_id"] == composition_id
    delivery = registry.execute(
        "paint.ui.motion.delivery.inspect",
        {"object_id": object_id},
    ).to_dict()
    assert delivery["ok"]
    assert delivery["result"]["composition_id"] == composition_id
    assert {
        row["target"] for row in delivery["result"]["targets"]
    } == {"web", "app", "umg"}
    binding_id = f"ui-binding-{object_id}"
    binding_report = registry.execute(
        "paint.ui.motion.binding.inspect",
        {},
    ).to_dict()
    assert binding_report["ok"]
    assert binding_report["result"]["links"][0]["binding_id"] == binding_id
    migrated = registry.execute(
        "paint.ui.motion.binding.migrate",
        {},
    ).to_dict()
    assert migrated["ok"]
    assert migrated["result"]["migrated_link_count"] == 0
    detached = registry.execute(
        "paint.ui.motion.binding.detach",
        {"object_id": object_id},
        confirm_destructive=True,
    ).to_dict()
    assert detached["ok"]
    assert detached["result"]["detached"] is True
    relinked = registry.execute(
        "paint.ui.motion.binding.relink",
        {
            "object_id": object_id,
            "composition_id": composition_id,
            "binding_id": binding_id,
        },
    ).to_dict()
    assert relinked["ok"]

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
    from app.painter_ui_document import UI_DOCUMENT_VERSION

    assert stored["ui_document"]["version"] == UI_DOCUMENT_VERSION == 31
    assert stored["ui_document"]["objects"][0]["name"] == "Continue"
    assert stored["ui_document"]["components"][0]["id"] == component_id
    assert stored["ui_document"]["tokens"][0]["id"] == token_id
    assert stored["ui_document"]["interactions"][0]["source_object_id"] == object_id
    stored_link = stored["ui_document"]["linked_targets"]["motion_designer"][
        "object_bindings"
    ][object_id]
    assert stored_link["composition_id"] == composition_id
    assert stored_link["binding_id"] == f"ui-binding-{object_id}"
    assert stored["ui_motion_compositions"][composition_id]["duration_ms"] == 800
    assert stored["workspace"]["mode"] == "ui_design"
    assert set(stored["workspace"]["ui_artboard_viewports"]) == {
        "artboard-1",
        desktop_id,
    }
    assert (
        stored["workspace"]["ui_artboard_viewports"]["artboard-1"][
            "zoom_percent"
        ]
        == phone_view["zoom_percent"]
    )
    assert (
        stored["workspace"]["ui_artboard_viewports"][desktop_id][
            "zoom_percent"
        ]
        == desktop_view["zoom_percent"]
    )

    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(document_path)
    restored_state = restored.painter_action_state()
    assert restored_state["workspace"]["mode"] == "ui_design"
    assert set(restored._painter_ui_artboard_viewports) == {
        "artboard-1",
        desktop_id,
    }
    assert (
        restored._painter_ui_artboard_viewports["artboard-1"][
            "zoom_percent"
        ]
        == phone_view["zoom_percent"]
    )
    assert restored_state["ui_design"]["validation"]["object_count"] == 1
    assert (
        restored_state["ui_design"]["document"]["objects"][0]["content"]["text"]
        == "Continue"
    )
    assert restored_state["ui_design"]["validation"]["component_count"] == 1
    assert restored_state["ui_design"]["validation"]["token_count"] == 1
    assert restored_state["ui_design"]["validation"]["interaction_count"] == 1
    assert composition_id in restored._painter_ui_motion_compositions
    assert (
        restored._painter_ui_motion_compositions[composition_id].duration_ms
        == 800
    )
    restored_link = restored._painter_ui_document["linked_targets"][
        "motion_designer"
    ]["object_bindings"][object_id]
    assert restored_link["binding_id"] == f"ui-binding-{object_id}"
    assert restored_link["composition_revision"] == (
        restored._painter_ui_motion_compositions[composition_id].revision
    )

    dialog.close()
    restored.close()
    dialog.deleteLater()
    restored.deleteLater()
    app.processEvents()


def test_painter_ui_design_toolbar_creates_edits_and_lists_visible_objects() -> None:
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
    assert dialog._painter_ui_overlay.tool() == "frame"
    dialog._create_painter_ui_object_from_rect("frame", 40, 50, 420, 280)
    dialog._ui_design_tool_buttons["text"].click()
    assert dialog._painter_ui_overlay.tool() == "text"
    dialog._create_painter_ui_object_from_rect("text", 72, 92, 320, 54)
    app.processEvents()
    state = dialog.painter_action_state()
    assert state["ui_design"]["validation"]["object_count"] == 2
    assert dialog._painter_ui_overlay.isVisible()
    assert dialog._paint_ui_inspector.isVisible()
    assert dialog._paint_ui_inspector.layer_list.count() == 2

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
    dialog._update_painter_ui_object_geometry(
        object_id,
        moved_row["x"],
        moved_row["y"],
        440.0,
        88.0,
    )
    resized = next(
        row
        for row in dialog.painter_action_state()["ui_design"]["document"]["objects"]
        if row["id"] == object_id
    )
    assert resized["width"] == 440.0
    assert resized["height"] == 88.0
    dialog._align_painter_ui_object(object_id, "hcenter")
    aligned = next(
        row
        for row in dialog.painter_action_state()["ui_design"]["document"]["objects"]
        if row["id"] == object_id
    )
    parent = next(
        row
        for row in dialog.painter_action_state()["ui_design"]["document"]["objects"]
        if row["id"] == aligned["parent_id"]
    )
    assert aligned["x"] == (
        parent["x"] + (parent["width"] - aligned["width"]) * 0.5
    )
    dialog._handle_painter_ui_key_command("right", True)
    nudged = next(
        row
        for row in dialog.painter_action_state()["ui_design"]["document"]["objects"]
        if row["id"] == object_id
    )
    assert nudged["x"] == aligned["x"] + 10.0
    dialog._duplicate_painter_ui_object(object_id)
    assert (
        dialog.painter_action_state()["ui_design"]["validation"]["object_count"]
        == 3
    )
    duplicate_id = dialog.painter_action_state()["ui_design"]["selected_object_id"]
    dialog._delete_painter_ui_object(duplicate_id)
    assert (
        dialog.painter_action_state()["ui_design"]["validation"]["object_count"]
        == 2
    )
    dialog._undo()
    assert (
        dialog.painter_action_state()["ui_design"]["validation"]["object_count"]
        == 3
    )

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_painter_ui_multi_select_align_distribute_and_group_undo() -> None:
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
    rows = []
    for x, y in ((60, 80), (310, 170), (650, 260)):
        dialog._create_painter_ui_object_from_rect(
            "rectangle",
            float(x),
            float(y),
            80.0,
            60.0,
        )
        rows.append(dialog.painter_action_state()["ui_design"]["selected_object_id"])

    dialog._set_painter_ui_selection(rows, rows[-1])
    app.processEvents()
    state = dialog.painter_action_state()["ui_design"]
    assert state["selected_object_ids"] == rows
    assert len(dialog._paint_ui_inspector.layer_list.selectedItems()) == 3

    dialog._align_painter_ui_object(rows[-1], "top")
    objects = {
        row["id"]: row
        for row in dialog.painter_action_state()["ui_design"]["document"]["objects"]
    }
    assert {objects[object_id]["y"] for object_id in rows} == {80.0}

    dialog._update_painter_ui_objects_batch(
        {
            rows[0]: {"x": 60.0},
            rows[1]: {"x": 250.0},
            rows[2]: {"x": 650.0},
        },
        label="Reset UI positions",
    )
    dialog._align_painter_ui_object(rows[-1], "distribute_h")
    objects = {
        row["id"]: row
        for row in dialog.painter_action_state()["ui_design"]["document"]["objects"]
    }
    ordered = sorted((objects[object_id] for object_id in rows), key=lambda row: row["x"])
    assert ordered[0]["x"] == 60.0
    assert ordered[-1]["x"] == 650.0
    gaps = [
        ordered[index + 1]["x"] - (ordered[index]["x"] + ordered[index]["width"])
        for index in range(2)
    ]
    assert abs(gaps[0] - gaps[1]) < 0.001

    before_move = {object_id: objects[object_id]["x"] for object_id in rows}
    dialog._update_painter_ui_objects_batch(
        {
            object_id: {"x": before_move[object_id] + 24.0}
            for object_id in rows
        },
        label="Move UI selection",
    )
    dialog._undo()
    undone = {
        row["id"]: row
        for row in dialog.painter_action_state()["ui_design"]["document"]["objects"]
    }
    assert {object_id: undone[object_id]["x"] for object_id in rows} == before_move

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_painter_ui_group_actions_preserve_children_and_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    dialog._set_canvas_workspace_mode("ui_design")
    registry = ActionRegistry(owner=dialog)
    object_ids = []
    for x in (80, 280, 480):
        result = registry.execute(
            "paint.ui.object.add",
            {
                "kind": "rectangle",
                "x": x,
                "y": 120,
                "width": 120,
                "height": 90,
            },
        ).to_dict()
        object_ids.append(result["result"]["ui_design"]["selected_object_id"])

    grouped = registry.execute(
        "paint.ui.object.group",
        {"object_ids": object_ids[:2], "name": "Cards"},
    ).to_dict()
    assert grouped["ok"]
    document = grouped["result"]["ui_design"]["document"]
    group_id = grouped["result"]["ui_design"]["selected_object_id"]
    assert next(row for row in document["objects"] if row["id"] == group_id)[
        "kind"
    ] == "group"
    assert {
        row["parent_id"]
        for row in document["objects"]
        if row["id"] in object_ids[:2]
    } == {group_id}

    reordered = registry.execute(
        "paint.ui.object.reorder",
        {"object_ids": [group_id], "command": "back"},
    ).to_dict()
    assert reordered["ok"]
    order = sorted(
        reordered["result"]["ui_design"]["document"]["objects"],
        key=lambda row: row["z_index"],
    )
    assert order[0]["id"] == group_id

    ungrouped = registry.execute(
        "paint.ui.object.ungroup",
        {"object_id": group_id},
    ).to_dict()
    assert ungrouped["ok"]
    assert group_id not in {
        row["id"]
        for row in ungrouped["result"]["ui_design"]["document"]["objects"]
    }
    assert set(ungrouped["result"]["ui_design"]["selected_object_ids"]) == set(
        object_ids[:2]
    )
    dialog._undo()
    assert group_id in {
        row["id"]
        for row in dialog.painter_action_state()["ui_design"]["document"]["objects"]
    }

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_painter_ui_layer_drop_reparents_and_action_moves_to_root() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    dialog._set_canvas_workspace_mode("ui_design")
    registry = ActionRegistry(owner=dialog)
    object_ids = []
    for x in (80, 280, 480):
        result = registry.execute(
            "paint.ui.object.add",
            {
                "kind": "rectangle",
                "x": x,
                "y": 120,
                "width": 120,
                "height": 90,
            },
        ).to_dict()
        object_ids.append(result["result"]["ui_design"]["selected_object_id"])
    grouped = registry.execute(
        "paint.ui.object.group",
        {"object_ids": object_ids[:2], "name": "Cards"},
    ).to_dict()
    group_id = grouped["result"]["ui_design"]["selected_object_id"]

    dialog._paint_ui_inspector.hierarchy_drop_requested.emit(
        [object_ids[2]],
        group_id,
        "inside",
    )
    app.processEvents()
    document = dialog.painter_action_state()["ui_design"]["document"]
    assert next(
        row for row in document["objects"] if row["id"] == object_ids[2]
    )["parent_id"] == group_id
    assert any(
        "  " in dialog._paint_ui_inspector.layer_list.item(index).text()
        for index in range(dialog._paint_ui_inspector.layer_list.count())
    )
    dialog._undo()
    document = dialog.painter_action_state()["ui_design"]["document"]
    assert next(
        row for row in document["objects"] if row["id"] == object_ids[2]
    )["parent_id"] == ""

    moved = registry.execute(
        "paint.ui.object.reparent",
        {
            "object_ids": [object_ids[0]],
            "placement": "root",
        },
    ).to_dict()
    assert moved["ok"]
    assert next(
        row
        for row in moved["result"]["ui_design"]["document"]["objects"]
        if row["id"] == object_ids[0]
    )["parent_id"] == ""

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_painter_ui_overlay_drag_create_move_and_resize_signals() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.show()
    app.processEvents()

    created: list[tuple] = []
    geometry: list[tuple] = []
    changes: list[tuple] = []
    overlay.object_create_requested.connect(lambda *args: created.append(args))
    overlay.object_geometry_requested.connect(lambda *args: geometry.append(args))
    overlay.object_changes_requested.connect(lambda *args: changes.append(args))

    overlay.set_tool("rectangle")
    overlay.set_snap(True, 8.0)
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(80, 90),
    )
    QTest.mouseMove(overlay, QPoint(300, 240))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(300, 240),
    )
    assert created
    assert created[0][0] == "rectangle"
    assert created[0][3] > 100
    assert created[0][4] > 100
    assert created[0][1] % 8.0 == 0.0
    assert created[0][2] % 8.0 == 0.0
    assert created[0][3] % 8.0 == 0.0
    assert created[0][4] % 8.0 == 0.0

    document, row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=100,
        y=100,
        width=200,
        height=120,
    )
    overlay.set_document(document)
    overlay.set_tool("select")
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(180, 150),
    )
    QTest.mouseMove(overlay, QPoint(240, 190))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(240, 190),
    )
    assert geometry
    assert geometry[-1][0] == row["id"]
    moved_width = geometry[-1][3]
    moved_height = geometry[-1][4]
    assert moved_width == 200.0
    assert moved_height == 120.0

    moved_document = document
    moved_document["objects"][0]["x"] = geometry[-1][1]
    moved_document["objects"][0]["y"] = geometry[-1][2]
    overlay.set_document(moved_document)
    bottom_right = QPoint(
        int(geometry[-1][1] + moved_width),
        int(geometry[-1][2] + moved_height),
    )
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        bottom_right,
    )
    QTest.mouseMove(overlay, bottom_right + QPoint(40, 30))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        bottom_right + QPoint(40, 30),
    )
    assert geometry[-1][3] > moved_width
    assert geometry[-1][4] > moved_height

    rotated_document, rotated_row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=300,
        y=200,
        width=120,
        height=80,
    )
    overlay.set_document(rotated_document)
    rotation_handle = QPoint(360, 180)
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        rotation_handle,
    )
    QTest.mouseMove(overlay, QPoint(430, 240))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(430, 240),
    )
    assert changes
    assert changes[-1][0] == rotated_row["id"]
    assert abs(float(changes[-1][1]["rotation"])) >= 80.0

    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_rectangle_radius_gizmo_drags_and_emits_style() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(640, 480),
        kind="rectangle",
        x=100,
        y=100,
        width=240,
        height=160,
        style={"fill": "#D9D9D9FF", "radius": 0},
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 480)
    overlay.set_document(document)
    overlay.set_tool("select")
    overlay.show()
    app.processEvents()

    changes: list[tuple] = []
    overlay.object_changes_requested.connect(lambda *args: changes.append(args))
    rect = overlay._object_rect(row)
    center = overlay._radius_handle_centers(row, rect)["nw"]
    start = QPoint(round(center.x()), round(center.y()))
    end = start + QPoint(50, 50)
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end, delay=1)
    assert overlay._interaction == "radius"
    assert overlay._radius_preview > 0
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)

    assert changes[-1][0] == row["id"]
    style = changes[-1][1]["style"]
    assert style["radius"] > 0
    assert len(set(style["corner_radii"].values())) == 1
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_ellipse_arc_gizmo_creates_arc_and_emits_content() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(640, 480),
        kind="ellipse",
        x=120,
        y=90,
        width=240,
        height=180,
        style={"fill": "#D9D9D9FF"},
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 480)
    overlay.set_document(document)
    # Figma keeps the ellipse tool active: selected-object gizmos still take
    # priority, while a drag on empty canvas creates another ellipse.
    overlay.set_tool("ellipse")
    overlay.show()
    app.processEvents()

    changes: list[tuple] = []
    overlay.object_changes_requested.connect(lambda *args: changes.append(args))
    rect = overlay._object_rect(row)
    handle = overlay._arc_handle_positions(row, rect)["sweep"]
    assert handle.x() < rect.right() - 8.0
    assert abs(handle.y() - rect.center().y()) < 0.001
    start = QPoint(round(handle.x()), round(handle.y()))
    end = QPoint(round(rect.center().x()), round(rect.bottom()))
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end, delay=1)
    assert overlay._interaction == "arc_sweep"
    preview = next(
        item for item in overlay._document["objects"] if item["id"] == row["id"]
    )
    assert preview["kind"] == "arc"
    assert -280.0 <= float(preview["content"]["sweep_angle"]) <= -260.0
    assert set(overlay._arc_handle_positions(preview, rect)) == {
        "start", "sweep", "ratio"
    }
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)

    assert changes[-1][0] == row["id"]
    assert changes[-1][1]["kind"] == "arc"
    assert -360.0 < changes[-1][1]["content"]["sweep_angle"] < 0.0
    assert overlay.tool() == "ellipse"
    created: list[tuple] = []
    overlay.object_create_requested.connect(lambda *args: created.append(args))
    blank_start = QPoint(40, 420)
    blank_end = QPoint(100, 460)
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=blank_start)
    QTest.mouseMove(overlay, blank_end, delay=1)
    assert overlay._interaction == "create"
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=blank_end)
    assert created[-1][0] == "ellipse"
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_arc_controls_support_positive_sweep_ratio_flip_and_closed_ring() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    ellipse_document, ellipse = add_ui_object(
        create_ui_document(640, 480),
        kind="ellipse", x=120, y=90, width=240, height=180,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 480)
    overlay.set_document(ellipse_document)
    overlay.set_tool("ellipse")
    overlay.show()
    app.processEvents()
    rect = overlay._object_rect(ellipse)
    sweep_handle = overlay._arc_handle_positions(ellipse, rect)["sweep"]
    QTest.mousePress(
        overlay, Qt.MouseButton.LeftButton, pos=sweep_handle.toPoint()
    )
    QTest.mouseMove(
        overlay,
        QPoint(round(rect.center().x()), round(rect.top())),
        delay=1,
    )
    positive_arc = next(
        row for row in overlay._document["objects"] if row["id"] == ellipse["id"]
    )
    assert 260.0 <= float(positive_arc["content"]["sweep_angle"]) <= 280.0
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(round(rect.center().x()), round(rect.top())),
    )

    arc_document, arc = add_ui_object(
        create_ui_document(640, 480),
        kind="arc", x=120, y=90, width=240, height=180,
        content={"start_angle": 0, "sweep_angle": 270, "inner_radius": 0},
    )
    overlay.set_document(arc_document)
    overlay.set_tool("select")
    rect = overlay._object_rect(arc)
    ratio_handle = overlay._arc_handle_positions(arc, rect)["ratio"]
    opposite = overlay._arc_point(rect, 315.0, 0.55).toPoint()
    QTest.mousePress(
        overlay, Qt.MouseButton.LeftButton, pos=ratio_handle.toPoint()
    )
    QTest.mouseMove(overlay, opposite, delay=1)
    flipped = next(
        row for row in overlay._document["objects"] if row["id"] == arc["id"]
    )
    assert -100.0 <= float(flipped["content"]["sweep_angle"]) <= -80.0
    assert 0.5 <= float(flipped["content"]["inner_radius"]) <= 0.6
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=opposite)

    ring_document, ring = add_ui_object(
        create_ui_document(640, 480),
        kind="arc", x=120, y=90, width=240, height=180,
        content={"start_angle": 0, "sweep_angle": 360, "inner_radius": 0.55},
    )
    overlay.set_document(ring_document)
    rect = overlay._object_rect(ring)
    assert set(overlay._arc_handle_positions(ring, rect)) == {
        "start", "sweep", "ratio",
    }
    ring_path = overlay._object_shape_path(ring)
    assert not ring_path.contains(rect.center())
    assert ring_path.contains(overlay._arc_point(rect, 90.0, 0.8))
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_shape_creation_preview_uses_geometry_and_line_endpoints() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(500, 400)

    def prime_preview(tool: str) -> None:
        overlay.set_tool(tool)
        overlay._interaction = "create"
        overlay._press_position = QPointF(80, 70)
        overlay._preview_line_end = QPointF(300, 210)
        overlay._preview_rect = QRectF(QPointF(80, 70), QPointF(300, 210))

    ellipse_image = QImage(500, 400, QImage.Format.Format_ARGB32_Premultiplied)
    ellipse_image.fill(Qt.GlobalColor.transparent)
    prime_preview("ellipse")
    painter = QPainter(ellipse_image)
    overlay._paint_creation_preview(painter)
    painter.end()
    assert ellipse_image.pixelColor(190, 140).alpha() > 0
    assert ellipse_image.pixelColor(84, 74).alpha() == 0

    line_image = QImage(500, 400, QImage.Format.Format_ARGB32_Premultiplied)
    line_image.fill(Qt.GlobalColor.transparent)
    prime_preview("arrow")
    painter = QPainter(line_image)
    overlay._paint_creation_preview(painter)
    painter.end()
    assert line_image.pixelColor(190, 140).alpha() > 0
    assert line_image.pixelColor(84, 204).alpha() == 0

    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_line_creation_emits_pointer_to_pointer_vector() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 480)
    overlay.set_document(create_ui_document(640, 480))
    overlay.set_tool("arrow")
    overlay.show()
    app.processEvents()
    created: list[tuple] = []
    overlay.object_create_requested.connect(lambda *args: created.append(args))
    start = QPoint(280, 220)
    end = QPoint(120, 220)
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end, delay=1)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)

    assert created[-1][0] == "arrow"
    assert created[-1][3] < 0.0
    assert created[-1][4] == 0.0
    overlay.close()
    overlay.deleteLater()

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 480, "#FFFFFF"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    dialog._create_painter_ui_object_from_rect("arrow", 280, 220, -160, 0)
    arrow = next(
        row for row in dialog._painter_ui_document["objects"]
        if row["name"] == "Arrow 1"
    )
    assert arrow["width"] == 160.0
    assert arrow["height"] == 1.0
    assert arrow["content"]["start_anchor"] == [1.0, 0.5]
    assert arrow["content"]["end_anchor"] == [0.0, 0.5]
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_star_and_line_canvas_gizmos_update_shape_content() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, star = add_ui_object(
        create_ui_document(700, 500), kind="star", x=120, y=100,
        width=220, height=220,
        content={"point_count": 5, "inner_radius": 0.45, "rotation_offset": -90},
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(700, 500)
    overlay.set_document(document)
    overlay.set_tool("select")
    overlay.show()
    app.processEvents()
    positions = overlay._shape_gizmo_positions(star, overlay._object_rect(star))
    assert set(positions) == {"shape_count", "shape_ratio", "shape_radius"}
    start = positions["shape_ratio"].toPoint()
    end = QPoint(round(overlay._object_rect(star).center().x() + 80), round(overlay._object_rect(star).center().y()))
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end, delay=1)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)
    updated_star = next(row for row in overlay._document["objects"] if row["id"] == star["id"])
    assert float(updated_star["content"]["inner_radius"]) > 0.45
    radius_position = overlay._shape_gizmo_positions(
        updated_star, overlay._object_rect(updated_star)
    )["shape_radius"]
    radius_end = QPoint(
        round(overlay._object_rect(updated_star).center().x()),
        round(overlay._object_rect(updated_star).center().y() - 18),
    )
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=radius_position.toPoint(),
    )
    QTest.mouseMove(overlay, radius_end, delay=1)
    assert overlay._interaction == "shape_radius"
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=radius_end)
    rounded_star = next(
        row for row in overlay._document["objects"] if row["id"] == star["id"]
    )
    assert float(rounded_star["content"]["corner_radius"]) > 20.0
    assert float(rounded_star["style"]["radius"]) == float(
        rounded_star["content"]["corner_radius"]
    )
    rounded_path = overlay._object_shape_path(rounded_star)
    assert any(
        rounded_path.elementAt(index).isCurveTo()
        for index in range(rounded_path.elementCount())
    )

    line_document, line = add_ui_object(
        create_ui_document(700, 500), kind="line", x=100, y=100,
        width=200, height=100, content={"arrow_end": True},
    )
    overlay.set_document(line_document)
    positions = overlay._shape_gizmo_positions(line, overlay._object_rect(line))
    assert set(positions) == {"line_start", "line_end"}
    start = positions["line_end"].toPoint()
    end = start + QPoint(60, -40)
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end, delay=1)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)
    updated_line = next(row for row in overlay._document["objects"] if row["id"] == line["id"])
    assert "start_anchor" in updated_line["content"]
    assert "end_anchor" in updated_line["content"]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_frame_tool_is_one_shot_and_can_draw_over_existing_objects() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rectangle = add_ui_object(
        create_ui_document(700, 500), kind="rectangle",
        x=180, y=140, width=220, height=160,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(700, 500)
    overlay.set_document(document)
    overlay.set_tool("frame")
    overlay.show()
    app.processEvents()
    center = overlay._object_rect(rectangle).center().toPoint()
    end = center + QPoint(100, 90)
    created: list[tuple] = []
    overlay.object_create_requested.connect(lambda *args: created.append(args))
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=center)
    assert overlay._interaction == "create"
    QTest.mouseMove(overlay, end, delay=1)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)
    assert created[-1][0] == "frame"

    overlay.set_document(document)
    overlay.set_tool("rectangle")
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=center)
    assert overlay._interaction != "create"
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=center)
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_real_painter_frame_creation_returns_toolbar_to_select() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(700, 500, "#FFFFFF"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    dialog._set_painter_ui_tool("frame")
    assert dialog._painter_ui_overlay.tool() == "frame"
    dialog._create_painter_ui_object_from_rect("frame", 40, 40, 300, 220)
    assert dialog._painter_ui_overlay.tool() == "select"
    dialog._set_painter_ui_tool("ellipse")
    dialog._create_painter_ui_object_from_rect("ellipse", 380, 40, 120, 120)
    assert dialog._painter_ui_overlay.tool() == "ellipse"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_real_painter_draws_rectangle_inside_frame_as_child_container_content() -> None:
    """Exercise the real dialog signal path, not only overlay helper methods."""
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    dialog.resize(1200, 820)
    dialog.show()
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._create_painter_ui_object_from_rect("frame", 120, 90, 420, 320)
    app.processEvents()

    frame = next(
        row for row in dialog._painter_ui_document["objects"]
        if row["kind"] == "frame"
    )
    overlay = dialog._painter_ui_overlay
    assert overlay._radius_eligible(frame) is False
    assert overlay._shape_gizmo_positions(
        frame, overlay._object_rect(frame)
    ) == {}
    assert overlay._arc_handle_positions(
        frame, overlay._object_rect(frame)
    ) == {}

    dialog._set_painter_ui_tool("rectangle")
    frame_rect = overlay._object_rect(frame)
    start = QPoint(
        round(frame_rect.left() + frame_rect.width() * 0.25),
        round(frame_rect.top() + frame_rect.height() * 0.25),
    )
    end = QPoint(
        round(frame_rect.left() + frame_rect.width() * 0.62),
        round(frame_rect.top() + frame_rect.height() * 0.58),
    )
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    assert overlay._interaction == "create"
    QTest.mouseMove(overlay, end, delay=1)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()

    rectangle = next(
        row for row in dialog._painter_ui_document["objects"]
        if row["kind"] == "rectangle"
    )
    assert rectangle["parent_id"] == frame["id"]
    assert dialog._painter_ui_overlay.tool() == "rectangle"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_painter_ui_overlay_preserves_active_artboard_aspect_ratio() -> None:
    app = _app()
    from app.painter_ui_document import (
        add_ui_artboard,
        create_ui_document,
        set_active_ui_artboard,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(1000, 700)
    document = create_ui_document(390, 844, name="Phone")
    phone_viewport, phone_scale = overlay._artboard_viewport()
    overlay.set_document(document)
    phone_viewport, phone_scale = overlay._artboard_viewport()
    assert abs(phone_viewport.width() / phone_viewport.height() - 390 / 844) < 0.001
    assert phone_scale > 0.0

    document, desktop = add_ui_artboard(
        document,
        name="Desktop",
        width=1440,
        height=900,
    )
    document = set_active_ui_artboard(document, desktop["id"])
    overlay.set_document(document)
    desktop_viewport, desktop_scale = overlay._artboard_viewport()
    assert abs(desktop_viewport.width() / desktop_viewport.height() - 1.6) < 0.001
    assert desktop_scale > 0.0
    assert desktop_viewport.width() > phone_viewport.width()

    overlay.deleteLater()
    app.processEvents()


def test_painter_ui_page_actions_scope_canvas_undo_and_round_trip(
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
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    page_one_object = registry.execute(
        "paint.ui.object.add",
        {"kind": "button", "name": "Page one CTA"},
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    added = registry.execute(
        "paint.ui.page.add",
        {"name": "Settings", "width": 1440, "height": 900},
    ).to_dict()
    assert added["ok"]
    page_two = added["result"]["ui_design"]["active_page_id"]
    assert page_two != "page-1"
    assert dialog._painter_ui_navigator.page_list.count() == 2
    assert {
        row["page_id"]
        for row in dialog._painter_ui_overlay._document["artboards"]
    } == {page_two}
    page_two_object = registry.execute(
        "paint.ui.object.add",
        {"kind": "text", "name": "Settings title"},
    ).to_dict()["result"]["ui_design"]["selected_object_id"]

    activated = registry.execute(
        "paint.ui.page.activate",
        {"page_id": "page-1"},
    ).to_dict()
    assert activated["ok"]
    assert activated["result"]["ui_design"]["active_page_id"] == "page-1"
    assert {
        row["id"] for row in dialog._painter_ui_overlay._document["objects"]
    } == {page_one_object}
    renamed = registry.execute(
        "paint.ui.page.update",
        {"page_id": "page-1", "changes": {"name": "Home"}},
    ).to_dict()
    assert renamed["ok"]
    assert renamed["result"]["ui_design"]["document"]["pages"][0]["name"] == "Home"

    removed = registry.execute(
        "paint.ui.page.remove",
        {"page_id": page_two},
    ).to_dict()
    assert removed["ok"]
    assert removed["result"]["ui_design"]["validation"]["page_count"] == 1
    dialog._undo()
    assert {row["id"] for row in dialog._painter_ui_document["pages"]} == {
        "page-1",
        page_two,
    }
    assert page_two_object in {
        row["id"] for row in dialog._painter_ui_document["objects"]
    }

    document_path = tmp_path / "pages.tspaint"
    dialog.save_document_to_path(document_path)
    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            64,
            64,
            "transparent",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(document_path)
    assert {row["id"] for row in restored._painter_ui_document["pages"]} == {
        "page-1",
        page_two,
    }
    assert restored._painter_ui_document["active_page_id"] == "page-1"

    dialog.close()
    restored.close()
    dialog.deleteLater()
    restored.deleteLater()
    app.processEvents()


def test_painter_ui_overlay_multi_artboard_fit_pan_and_activation() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import (
        add_ui_artboard,
        create_ui_document,
        set_active_ui_artboard,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(390, 844, name="Phone")
    document, desktop = add_ui_artboard(
        document,
        name="Desktop",
        width=1440,
        height=900,
    )
    document = set_active_ui_artboard(document, "artboard-1")
    overlay = PainterUIDesignOverlay()
    overlay.resize(1000, 700)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()

    phone_viewport, all_scale = overlay._artboard_viewport(document["artboards"][0])
    desktop_viewport, desktop_scale = overlay._artboard_viewport(desktop)
    assert all_scale == desktop_scale
    assert phone_viewport.right() < desktop_viewport.left()

    overlay.fit_artboard(desktop["id"])
    assert overlay.view_state()["scale"] > all_scale
    before = overlay.view_state()
    QTest.mousePress(
        overlay,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(500, 350),
    )
    QTest.mouseMove(overlay, QPoint(540, 380))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(540, 380),
    )
    after = overlay.view_state()
    assert after["offset_x"] > before["offset_x"]
    assert after["offset_y"] > before["offset_y"]

    activated: list[str] = []
    overlay.artboard_activation_requested.connect(activated.append)
    overlay.fit_all()
    desktop_viewport, _scale = overlay._artboard_viewport(desktop)
    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        desktop_viewport.center().toPoint(),
    )
    assert activated == [desktop["id"]]

    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_painter_ui_overlay_view_state_restores_world_center_after_resize() -> None:
    app = _app()
    from app.drawing import PaintDialog
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    normalized = PaintDialog._normalize_painter_ui_artboard_viewports(
        {
            "artboard-1": {
                "zoom_percent": "not-a-number",
                "center_x": "12.5",
                "center_y": None,
            },
            "removed-artboard": {"zoom_percent": 200},
        },
        valid_artboard_ids={"artboard-1"},
    )
    assert normalized == {
        "artboard-1": {
            "zoom_percent": 100.0,
            "center_x": 12.5,
            "center_y": 0.0,
        }
    }

    overlay = PainterUIDesignOverlay()
    overlay.resize(720, 520)
    overlay.set_document(create_ui_document(390, 844))
    overlay.fit_artboard()
    overlay.set_zoom_percent(143)
    overlay.pan_view(dx=37, dy=-29)
    saved = overlay.view_state()

    overlay.resize(1180, 760)
    restored = overlay.set_view_state(saved)
    assert restored["zoom_percent"] == 143.0
    assert abs(restored["center_x"] - saved["center_x"]) < 0.001
    assert abs(restored["center_y"] - saved["center_y"]) < 0.001
    assert restored["offset_x"] != saved["offset_x"]
    assert restored["offset_y"] != saved["offset_y"]

    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_painter_ui_overlay_uses_canvas_first_wheel_navigation() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 640)
    overlay.set_document(create_ui_document(390, 844))
    overlay.fit_artboard()
    overlay.show()
    app.processEvents()

    anchor = QPointF(340.0, 260.0)
    before = overlay.view_state()
    world_before = (
        (anchor.x() - before["offset_x"]) / before["scale"],
        (anchor.y() - before["offset_y"]) / before["scale"],
    )
    zoom_event = QWheelEvent(
        anchor,
        overlay.mapToGlobal(anchor.toPoint()),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    overlay.wheelEvent(zoom_event)
    zoomed = overlay.view_state()
    world_after = (
        (anchor.x() - zoomed["offset_x"]) / zoomed["scale"],
        (anchor.y() - zoomed["offset_y"]) / zoomed["scale"],
    )
    assert zoomed["scale"] > before["scale"]
    assert abs(world_after[0] - world_before[0]) < 0.001
    assert abs(world_after[1] - world_before[1]) < 0.001

    vertical_event = QWheelEvent(
        anchor,
        overlay.mapToGlobal(anchor.toPoint()),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    overlay.wheelEvent(vertical_event)
    vertical = overlay.view_state()
    assert vertical["scale"] == zoomed["scale"]
    assert vertical["offset_y"] > zoomed["offset_y"]

    horizontal_event = QWheelEvent(
        anchor,
        overlay.mapToGlobal(anchor.toPoint()),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    overlay.wheelEvent(horizontal_event)
    horizontal = overlay.view_state()
    assert horizontal["offset_x"] > vertical["offset_x"]
    assert horizontal["offset_y"] == vertical["offset_y"]

    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_painter_ui_hand_tool_pans_with_left_drag() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 640)
    overlay.set_document(create_ui_document(390, 844))
    overlay.fit_artboard()
    overlay.show()
    app.processEvents()

    assert overlay.set_tool("pan") == "pan"
    assert overlay.cursor().shape() == Qt.CursorShape.OpenHandCursor
    before = overlay.view_state()
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(420, 300),
    )
    assert overlay.cursor().shape() == Qt.CursorShape.ClosedHandCursor
    QTest.mouseMove(overlay, QPoint(470, 340))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(470, 340),
    )
    after = overlay.view_state()

    assert after["offset_x"] > before["offset_x"]
    assert after["offset_y"] > before["offset_y"]
    assert overlay.cursor().shape() == Qt.CursorShape.OpenHandCursor
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_painter_ui_overlay_native_gestures_preserve_focus_and_clamp() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, Qt

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 640)
    overlay.set_document(create_ui_document(390, 844))
    overlay.fit_artboard()
    anchor = QPointF(450.0, 320.0)
    before = overlay.view_state()
    world_before = QPointF(
        (anchor.x() - before["offset_x"]) / before["scale"],
        (anchor.y() - before["offset_y"]) / before["scale"],
    )
    assert overlay.apply_native_gesture(
        Qt.NativeGestureType.ZoomNativeGesture,
        value=0.18,
        position=anchor,
    )
    zoomed = overlay.view_state()
    world_after = QPointF(
        (anchor.x() - zoomed["offset_x"]) / zoomed["scale"],
        (anchor.y() - zoomed["offset_y"]) / zoomed["scale"],
    )
    assert zoomed["scale"] > before["scale"]
    assert abs(world_after.x() - world_before.x()) < 0.001
    assert abs(world_after.y() - world_before.y()) < 0.001

    assert overlay.apply_native_gesture(
        Qt.NativeGestureType.PanNativeGesture,
        delta=QPointF(12.25, -7.5),
    )
    panned = overlay.view_state()
    assert abs(panned["offset_x"] - zoomed["offset_x"] - 12.25) < 0.001
    assert abs(panned["offset_y"] - zoomed["offset_y"] + 7.5) < 0.001

    overlay.pan_view(x=1_000_000.0, y=-1_000_000.0)
    clamped = overlay.view_state()
    bounds = overlay._scene_bounds()
    assert bounds.left() * clamped["scale"] + clamped["offset_x"] <= 876.0
    assert bounds.right() * clamped["scale"] + clamped["offset_x"] >= 24.0
    assert bounds.top() * clamped["scale"] + clamped["offset_y"] <= 616.0
    assert bounds.bottom() * clamped["scale"] + clamped["offset_y"] >= 24.0

    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_painter_ui_overlay_marquee_selection_emits_replace_then_add() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(800, 600)
    document, first = add_ui_object(
        document, kind="rectangle", x=100, y=100, width=100, height=80
    )
    document, second = add_ui_object(
        document, kind="rectangle", x=260, y=120, width=100, height=80
    )
    document["selection"] = {"object_id": "", "object_ids": []}
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[tuple[str, str]] = []
    overlay.object_selection_requested.connect(
        lambda object_id, mode: emitted.append((object_id, mode))
    )

    first_rect = overlay._object_rect(first)
    second_rect = overlay._object_rect(second)
    start = QPoint(
        int(first_rect.left() - 12),
        int(first_rect.top() - 12),
    )
    end = QPoint(
        int(second_rect.right() + 12),
        int(second_rect.bottom() + 12),
    )
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)
    assert emitted == [(first["id"], "replace"), (second["id"], "add")]

    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_painter_ui_overlay_resize_constraints_and_smart_guides() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, QRectF, Qt

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay._original_rect = QRectF(100, 100, 200, 100)
    overlay._active_handle = "se"
    ratio_rect = overlay._resize_rect(
        QPointF(360, 260),
        Qt.KeyboardModifier.ShiftModifier,
    )
    assert abs(ratio_rect.width() / ratio_rect.height() - 2.0) < 0.001
    centered_rect = overlay._resize_rect(
        QPointF(360, 220),
        Qt.KeyboardModifier.AltModifier,
    )
    assert centered_rect.center() == overlay._original_rect.center()

    document = create_ui_document(800, 600)
    document, moving = add_ui_object(
        document, kind="rectangle", x=80, y=100, width=100, height=80
    )
    document, _target = add_ui_object(
        document, kind="rectangle", x=300, y=100, width=100, height=80
    )
    overlay.set_document(document)
    overlay.set_snap(True, 8.0)
    overlay._move_original_positions = {moving["id"]: (80.0, 100.0)}
    snapped_x, snapped_y = overlay._smart_snap_position(moving, 198.0, 100.0)
    assert snapped_x == 200.0
    assert snapped_y == 100.0
    assert overlay._guide_x is not None
    assert overlay._guide_y is not None

    overlay.deleteLater()
    app.processEvents()
