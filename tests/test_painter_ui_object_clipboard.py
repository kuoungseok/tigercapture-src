from __future__ import annotations

import copy
import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _instance_document():
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_interaction,
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(900, 640)
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Button",
        x=80,
        y=80,
        width=160,
        height=48,
    )
    document, _label = add_ui_object(
        document,
        kind="text",
        name="Label",
        parent_id=root["id"],
        x=120,
        y=94,
        width=80,
        height=20,
        content={"text": "Continue"},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Button",
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=component["id"],
        x=360,
        y=220,
    )
    document, _ = update_ui_object(
        document,
        instance["root_object_id"],
        {"opacity": 0.72},
    )
    document, _interaction = add_ui_interaction(
        document,
        source_object_id=instance["root_object_id"],
        trigger="click",
        action="set_visibility",
        target_object_id=root["id"],
    )
    document["selection"] = {
        "object_id": instance["root_object_id"],
        "object_ids": [instance["root_object_id"]],
    }
    return document, component, instance


def test_object_clipboard_pastes_linked_instance_with_new_stable_ids() -> None:
    import json

    from app.painter_ui_document import normalize_ui_document, validate_ui_document
    from app.painter_ui_object_clipboard import (
        copy_ui_selection_payload,
        paste_ui_selection_payload,
    )

    document, component, instance = _instance_document()
    payload = copy_ui_selection_payload(document)
    updated, report = paste_ui_selection_payload(document, payload)
    created_root_id = report["created_root_object_ids"][0]
    assert created_root_id != instance["root_object_id"]
    assert not set(report["created_object_ids"]) & {
        row["id"] for row in document["objects"]
    }
    pasted_root = next(row for row in updated["objects"] if row["id"] == created_root_id)
    pasted_children = [
        row for row in updated["objects"] if row["parent_id"] == created_root_id
    ]
    assert pasted_root["component_role"] == "instance"
    assert pasted_root["component_id"] == component["id"]
    assert pasted_root["opacity"] == 0.72
    assert pasted_root["x"] == 372.0
    assert pasted_root["y"] == 232.0
    assert len(pasted_children) == 1
    pasted_interaction = next(
        row
        for row in updated["interactions"]
        if row["source_object_id"] == created_root_id
    )
    assert pasted_interaction["id"] not in {
        row["id"] for row in document["interactions"]
    }
    assert validate_ui_document(updated)["ok"] is True
    reloaded = normalize_ui_document(json.loads(json.dumps(updated)))
    assert next(row for row in reloaded["objects"] if row["id"] == created_root_id)[
        "component_id"
    ] == component["id"]


def test_whole_object_clipboard_survives_native_tspaint_round_trip(
    tmp_path,
) -> None:
    from app.painter_document_io import (
        load_painter_document,
        save_painter_document,
    )
    from app.painter_ui_document import validate_ui_document
    from app.painter_ui_object_clipboard import (
        copy_ui_selection_payload,
        paste_ui_selection_payload,
    )

    document, component, _instance = _instance_document()
    payload = copy_ui_selection_payload(document)
    updated, paste_report = paste_ui_selection_payload(document, payload)
    pasted_root_id = paste_report["created_root_object_ids"][0]
    pasted_interaction_id = next(
        iter(paste_report["interaction_id_map"].values())
    )
    path = tmp_path / "m3-component-clipboard.tspaint"

    save_report = save_painter_document(
        path,
        {
            "workspace": {"mode": "ui_design"},
            "ui_document": updated,
        },
    )
    restored_payload, load_report = load_painter_document(path)
    restored = restored_payload["ui_document"]

    assert save_report["format"] == "tigerstudio.painter.document.v3"
    assert load_report["format"] == "tigerstudio.painter.document.v3"
    assert validate_ui_document(restored)["ok"] is True
    assert restored["version"] == updated["version"]
    pasted_root = next(
        row for row in restored["objects"] if row["id"] == pasted_root_id
    )
    assert pasted_root["component_id"] == component["id"]
    assert pasted_root["component_role"] == "instance"
    assert pasted_root["opacity"] == 0.72
    pasted_child = next(
        row for row in restored["objects"] if row["parent_id"] == pasted_root_id
    )
    assert pasted_child["component_role"] == "instance"
    pasted_interaction = next(
        row
        for row in restored["interactions"]
        if row["id"] == pasted_interaction_id
    )
    assert pasted_interaction["source_object_id"] == pasted_root_id


def test_design_mode_ctrl_copy_paste_path_is_one_undo_step() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, _component, instance = _instance_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 640, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    dialog._canvas_workspace_mode = "ui_design"
    undo_count = len(dialog._undo_labels)
    dialog._copy_selected_layer()
    dialog._paste_layer_clipboard()

    pasted_id = dialog._painter_ui_document["selection"]["object_id"]
    assert pasted_id != instance["root_object_id"]
    assert len(dialog._undo_labels) == undo_count + 1
    dialog._undo()
    assert all(
        row["id"] != pasted_id for row in dialog._painter_ui_document["objects"]
    )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
