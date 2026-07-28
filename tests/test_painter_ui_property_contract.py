from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _conflicted_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, parent = add_ui_object(
        document,
        kind="frame",
        width=320,
        height=120,
    )
    document["objects"][-1]["layout"] = {
        "mode": "horizontal",
        "width_sizing": "hug",
        "gap": 12,
    }
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=100,
        height=60,
    )
    document["objects"][-1]["layout"] = {"width_sizing": "fill"}
    return document, parent, child


def test_property_inspect_reports_default_token_and_related_diagnostics() -> None:
    from app.painter_ui_property_contract import inspect_ui_property

    document, parent, child = _conflicted_document()
    document["objects"][-1]["token_bindings"] = {
        "layout.width_sizing": "token-layout-fill"
    }
    report = inspect_ui_property(
        document,
        child["id"],
        "layout.width_sizing",
    )
    assert report["schema"] == "tigerstudio.painter.ui.property.v1"
    assert report["value"] == "fill"
    assert report["default"] == "fixed"
    assert report["resettable"] is True
    assert report["token_id"] == "token-layout-fill"
    assert any(
        item["code"] == "layout_hug_fill_cycle"
        and item["owner_id"] == parent["id"]
        for item in report["diagnostics"]
    )


def test_property_reset_preserves_layout_and_returns_normalized_report() -> None:
    from app.painter_ui_property_contract import reset_ui_property

    document, parent, _child = _conflicted_document()
    original_layout = dict(document["objects"][0]["layout"])
    updated, report = reset_ui_property(
        document,
        parent["id"],
        "layout.width_sizing",
    )
    row = next(item for item in updated["objects"] if item["id"] == parent["id"])
    assert row["layout"]["width_sizing"] == "fixed"
    assert row["layout"]["gap"] == original_layout["gap"]
    assert report["is_default"] is True
    assert report["diagnostics"] == []


def test_property_actions_share_object_update_and_one_step_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._add_default_painter_ui_object("frame")
    row = dialog._painter_ui_document["objects"][-1]
    dialog._update_painter_ui_object_changes(
        row["id"],
        {
            "layout": {
                **row["layout"],
                "mode": "horizontal",
                "width_sizing": "hug",
            }
        },
    )
    registry = ActionRegistry(owner=dialog)
    action_ids = {item["id"] for item in registry.list_actions()}
    assert "paint.ui.property.inspect" in action_ids
    assert "paint.ui.property.reset" in action_ids
    before_reset = dict(dialog._painter_ui_document["objects"][-1]["layout"])

    inspected = registry.execute(
        "paint.ui.property.inspect",
        {
            "object_id": row["id"],
            "property_path": "layout.width_sizing",
        },
    ).to_dict()
    assert inspected["ok"] is True
    assert inspected["result"]["value"] == "hug"

    reset = registry.execute(
        "paint.ui.property.reset",
        {
            "object_id": row["id"],
            "property_path": "layout.width_sizing",
        },
    ).to_dict()
    assert reset["ok"] is True
    assert reset["result"]["property"]["value"] == "fixed"
    dialog._undo()
    assert dialog._painter_ui_document["objects"][-1]["layout"] == before_reset
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_sizing_control_and_inspector_show_visual_state_and_recovery() -> None:
    app = _app()
    from app.painter_ui_document import select_ui_object
    from app.painter_ui_inspector import PainterUIInspector
    from app.painter_ui_sizing_control import PainterUISizingControl

    control = PainterUISizingControl("W")
    values: list[str] = []
    control.value_changed.connect(values.append)
    control._buttons["hug"].click()
    assert control.value() == "hug"
    assert values == ["hug"]
    assert control._buttons["hug"].isChecked()

    document, parent, _child = _conflicted_document()
    document = select_ui_object(document, parent["id"])
    inspector = PainterUIInspector()
    inspector.set_document(document)
    assert inspector.auto_layout_width_sizing_control.value() == "hug"
    assert "layout error" in inspector.auto_layout_status_label.text()
    assert "Use Fixed on the parent axis" in (
        inspector.auto_layout_status_label.toolTip()
    )
    inspector.auto_layout_width_sizing_control._buttons["fixed"].click()
    assert (
        inspector.auto_layout_width_sizing_combo.currentData()
        == "fixed"
    )
    control.deleteLater()
    inspector.deleteLater()
    app.processEvents()
