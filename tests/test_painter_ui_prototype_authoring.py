from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_prototype_flow_and_transition_round_trip() -> None:
    from app.painter_ui_document import (
        add_ui_interaction,
        add_ui_object,
        create_ui_document,
        normalize_ui_document,
        validate_ui_document,
    )
    from app.painter_ui_prototype_authoring import (
        add_ui_prototype_flow,
        inspect_ui_prototype_authoring,
        reorder_ui_prototype_interaction,
        set_ui_prototype_transition,
    )

    document, button = add_ui_object(
        create_ui_document(390, 844),
        kind="button",
        name="Continue",
    )
    document, interaction = add_ui_interaction(
        document,
        source_object_id=button["id"],
        trigger="click",
        action="navigate",
        target_artboard_id="artboard-1",
    )
    document, flow = add_ui_prototype_flow(
        document,
        name="Checkout",
        artboard_id="artboard-1",
        start_object_id=button["id"],
        device_preset="iPhone 390 x 844",
    )
    document, _interaction = set_ui_prototype_transition(
        document,
        interaction["id"],
        {
            "kind": "smart_animate",
            "duration_ms": 320,
            "easing": "ease_in_out",
            "direction": "left",
        },
    )
    report = inspect_ui_prototype_authoring(
        document,
        object_id=button["id"],
    )
    assert report["active_flow_id"] == flow["id"]
    assert report["interactions"][0]["transition"]["kind"] == "smart_animate"
    assert report["interactions"][0]["transition"]["duration_ms"] == 320
    assert report["interactions"][0]["smart_animate"]["status"] == "fallback"
    assert (
        "no_stable_component_matches"
        in report["interactions"][0]["smart_animate"]["fallback_reasons"]
    )
    assert validate_ui_document(document)["ok"] is True
    assert normalize_ui_document(document) == document
    document, second_interaction = add_ui_interaction(
        document,
        source_object_id=button["id"],
        trigger="click",
        action="play_sound",
        parameters={"uri": "click.wav"},
    )
    document, reorder = reorder_ui_prototype_interaction(
        document,
        second_interaction["id"],
        -1,
    )
    assert reorder["to_index"] == 0
    assert document["interactions"][0]["id"] == second_interaction["id"]


def test_prototype_authoring_actions_share_document_and_undo() -> None:
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
    object_id = registry.execute(
        "paint.ui.object.add",
        {"kind": "button", "name": "Continue"},
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    interaction = registry.execute(
        "paint.ui.interaction.add",
        {
            "source_object_id": object_id,
            "trigger": "mouse_enter",
            "action": "change_variant",
            "target_object_id": object_id,
            "parameters": {"variant": "Hover"},
        },
    ).to_dict()
    interaction_id = interaction["result"]["ui_design"]["document"][
        "interactions"
    ][0]["id"]
    second = registry.execute(
        "paint.ui.interaction.add",
        {
            "source_object_id": object_id,
            "trigger": "click",
            "action": "play_sound",
            "parameters": {"uri": "click.wav"},
        },
    ).to_dict()
    second_id = second["result"]["ui_design"]["document"]["interactions"][1][
        "id"
    ]
    reordered_action = registry.execute(
        "paint.ui.prototype.connection.reorder",
        {"interaction_id": second_id, "direction": -1},
    ).to_dict()
    assert reordered_action["ok"] is True
    assert reordered_action["result"]["reorder"]["to_index"] == 0
    flow = registry.execute(
        "paint.ui.prototype.flow.add",
        {
            "name": "Primary Flow",
            "artboard_id": "artboard-1",
            "start_object_id": object_id,
        },
    ).to_dict()
    assert flow["ok"] is True
    transition = registry.execute(
        "paint.ui.prototype.transition.set",
        {
            "interaction_id": interaction_id,
            "transition": {
                "kind": "dissolve",
                "duration_ms": 180,
                "easing": "ease_out",
            },
        },
    ).to_dict()
    assert transition["ok"] is True
    inspected = registry.execute(
        "paint.ui.prototype.authoring.inspect",
        {"object_id": object_id},
    ).to_dict()
    assert inspected["result"]["interaction_count"] == 2
    transition_row = next(
        row
        for row in inspected["result"]["interactions"]
        if row["id"] == interaction_id
    )
    assert transition_row["transition"]["kind"] == "dissolve"
    dialog._set_painter_ui_prototype_preview(True)
    dialog._execute_painter_ui_prototype_trigger(
        object_id,
        "click",
        "",
    )
    assert dialog._painter_ui_prototype_state["events"][-1]["action"] == "play_sound"
    assert dialog._painter_ui_overlay.prototype_preview_enabled() is True
    assert dialog._paint_ui_inspector.prototype_panel.preview_check.isChecked()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_compact_prototype_panel_emits_connection_flow_and_transition() -> None:
    app = _app()
    from app.painter_ui_document import (
        add_ui_interaction,
        add_ui_object,
        create_ui_document,
    )
    from app.painter_ui_prototype_panel import PainterUIPrototypePanel

    document, button = add_ui_object(
        create_ui_document(390, 844),
        kind="button",
        name="Continue",
    )
    document, _interaction = add_ui_interaction(
        document,
        source_object_id=button["id"],
        trigger="click",
        action="navigate",
        target_artboard_id="artboard-1",
    )
    document["selection"] = {
        "object_id": button["id"],
        "object_ids": [button["id"]],
    }
    panel = PainterUIPrototypePanel()
    panel.set_document(document)
    added: list[dict] = []
    transitions: list[tuple[str, dict]] = []
    flows: list[dict] = []
    reordered: list[tuple[str, int]] = []
    preview: list[bool] = []
    resets: list[bool] = []
    panel.connection_add_requested.connect(added.append)
    panel.transition_set_requested.connect(
        lambda interaction_id, value: transitions.append(
            (interaction_id, value)
        )
    )
    panel.flow_add_requested.connect(flows.append)
    panel.connection_reorder_requested.connect(
        lambda interaction_id, direction: reordered.append(
            (interaction_id, direction)
        )
    )
    panel.preview_changed.connect(preview.append)
    panel.preview_reset_requested.connect(lambda: resets.append(True))
    panel.add_button.click()
    panel.connection_list.setCurrentRow(0)
    panel.transition_combo.setCurrentIndex(
        panel.transition_combo.findData("dissolve")
    )
    panel.duration_spin.setValue(220)
    panel.transition_button.click()
    panel.flow_add_button.click()
    panel.move_down_button.click()
    panel.preview_check.click()
    panel.set_preview_state(
        {
            "artboard_id": "artboard-1",
            "variables": {"theme": "dark"},
            "events": [{"action": "navigate"}],
        },
        enabled=True,
    )
    panel.preview_reset_button.click()
    app.processEvents()
    assert added[0]["source_object_id"] == button["id"]
    assert transitions[0][1]["kind"] == "dissolve"
    assert transitions[0][1]["duration_ms"] == 220
    assert flows[0]["start_object_id"] == button["id"]
    assert reordered[0][1] == 1
    assert preview == [True]
    assert resets == [True]
    assert "1 vars" in panel.preview_state_label.text()
    panel.close()
    panel.deleteLater()
    app.processEvents()


def test_inline_preview_runs_scoped_delay_interaction() -> None:
    app = _app()
    from PySide6.QtTest import QTest

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    object_id = registry.execute(
        "paint.ui.object.add",
        {"kind": "button", "name": "Delayed"},
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    registry.execute(
        "paint.ui.interaction.add",
        {
            "source_object_id": object_id,
            "trigger": "delay",
            "action": "play_sound",
            "parameters": {"delay_ms": 5, "uri": "ready.wav"},
        },
    )

    dialog._set_painter_ui_prototype_preview(True)
    QTest.qWait(100)

    assert dialog._painter_ui_prototype_state["events"][-1]["action"] == "play_sound"
    assert len(dialog._painter_ui_prototype_state["events"]) == 1
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
