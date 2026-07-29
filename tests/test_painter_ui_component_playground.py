from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _component_document() -> tuple[dict, dict, dict]:
    from app.painter_ui_components import (
        bind_ui_component_property,
        convert_ui_object_to_component,
        define_ui_component_property,
        set_ui_component_state_override,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(640, 480)
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Button Card",
        x=40,
        y=40,
        width=280,
        height=120,
        style={"fill": "#1C2938"},
    )
    document, label = add_ui_object(
        document,
        kind="text",
        name="Label",
        parent_id=root["id"],
        x=64,
        y=72,
        width=180,
        height=36,
        content={"text": "Profile"},
        style={"text_color": "#FFFFFF", "font_size": 18},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Button Card",
    )
    document, _ = define_ui_component_property(
        document,
        component_id=component["id"],
        property_name="Label",
        definition={"type": "text", "default": "Profile"},
    )
    document, _ = bind_ui_component_property(
        document,
        component_id=component["id"],
        source_object_id=label["id"],
        property_name="Label",
        target_path="content.text",
    )
    document, _ = set_ui_component_state_override(
        document,
        component_id=component["id"],
        state="hover",
        source_object_id=root["id"],
        changes={"opacity": 0.55},
    )
    document["selection"] = {
        "object_id": root["id"],
        "object_ids": [root["id"]],
    }
    return document, component, label


def test_component_playground_materializes_values_without_source_mutation() -> None:
    from app.painter_ui_component_playground import (
        build_ui_component_playground,
    )

    document, component, _label = _component_document()
    original = copy.deepcopy(document)
    preview, report = build_ui_component_playground(
        document,
        component_id=component["id"],
        property_values={"Label": "Preview label", "state": "hover"},
    )

    assert document == original
    assert preview["revision"] == document["revision"]
    assert preview["selection"]["object_ids"] == []
    assert preview["components"] == []
    assert report["preview_only"] is True
    assert report["property_values"]["Label"] == "Preview label"
    preview_label = next(row for row in preview["objects"] if row["kind"] == "text")
    preview_root = next(row for row in preview["objects"] if row["parent_id"] == "")
    assert preview_label["content"]["text"] == "Preview label"
    assert preview_root["opacity"] == 0.55
    assert all(row["component_role"] == "none" for row in preview["objects"])


def test_component_playground_panel_and_inspector_button_are_contextual() -> None:
    app = _app()
    from app.painter_ui_component_playground_panel import (
        PainterUIComponentPlaygroundPanel,
    )
    from app.painter_ui_inspector import PainterUIInspector

    document, component, _label = _component_document()
    panel = PainterUIComponentPlaygroundPanel()
    panel.set_component(document, component["id"])
    panel.show()
    app.processEvents()
    assert {"state", "Label"} <= set(panel._controls)
    panel._set_property("Label", "Panel preview")
    assert panel.report()["property_values"]["Label"] == "Panel preview"

    inspector = PainterUIInspector()
    requests: list[str] = []
    inspector.component_playground_requested.connect(requests.append)
    inspector.set_document(document)
    inspector.component_playground_button.click()
    assert requests == [component["id"]]

    panel.close()
    panel.deleteLater()
    inspector.deleteLater()
    app.processEvents()


def test_component_playground_action_is_read_only() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, component, _label = _component_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 480, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    before = copy.deepcopy(document)
    undo_count = len(dialog._undo_stack)
    result = ActionRegistry(owner=dialog).execute(
        "paint.ui.component.playground.inspect",
        {
            "component_id": component["id"],
            "property_values": {"Label": "Action preview"},
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["property_values"]["Label"] == "Action preview"
    assert dialog._painter_ui_document == before
    assert len(dialog._undo_stack) == undo_count
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
