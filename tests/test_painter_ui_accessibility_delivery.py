from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_accessibility_normalization_and_focus_order_validation() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
        validate_ui_document,
    )

    document = create_ui_document(390, 844)
    document, image = add_ui_object(
        document,
        kind="image",
        name="Product",
    )
    document, first = add_ui_object(
        document,
        kind="button",
        name="Buy",
        content={"text": "Buy now"},
    )
    document, second = add_ui_object(
        document,
        kind="button",
        name="Details",
        content={"text": "Details"},
    )
    document, image = update_ui_object(
        document,
        image["id"],
        {
            "accessibility": {
                "role": "IMAGE",
                "label": " Product preview ",
                "focus_order": "2",
            }
        },
    )
    document, first = update_ui_object(
        document,
        first["id"],
        {"accessibility": {"role": "button", "focus_order": 1}},
    )
    document, second = update_ui_object(
        document,
        second["id"],
        {"accessibility": {"role": "link", "focus_order": 1}},
    )

    assert image["accessibility"] == {
        "role": "image",
        "label": "Product preview",
        "focus_order": 2,
    }
    validation = validate_ui_document(document)
    assert f"missing_accessibility_label:{second['id']}" in validation["warnings"]
    assert any(
        warning.startswith("duplicate_focus_order:artboard-1:1:")
        for warning in validation["warnings"]
    )
    assert f"missing_accessibility_label:{first['id']}" not in validation["warnings"]


def test_delivery_statuses_use_native_material_baked_blocked_contract() -> None:
    from app.painter_ui_delivery import (
        preflight_ui_delivery,
        ui_object_delivery_statuses,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document()
    document, rectangle = add_ui_object(
        document,
        kind="rectangle",
        name="Panel",
    )
    statuses = ui_object_delivery_statuses(document, rectangle["id"])
    by_target = {
        row["target"]: row["disposition"] for row in statuses["targets"]
    }
    assert by_target == {
        "asset_export": "native",
        "design_handoff": "native",
        "review_prototype": "native",
        "unreal_umg": "material",
    }

    document["objects"][0]["style"]["paint_layer_id"] = "paint-layer-1"
    baked = preflight_ui_delivery(document, "unreal_umg")
    assert baked["schema"] == "tigerstudio.painter.ui.delivery_preflight.v2"
    assert baked["counts"] == {
        "native": 0,
        "material": 0,
        "baked": 1,
        "blocked": 0,
    }
    assert baked["objects"][0]["display_disposition"] == "Baked"

    document["objects"][0]["kind"] = "future-widget"
    document["objects"][0]["style"] = {}
    blocked = preflight_ui_delivery(document, "unreal_umg")
    assert blocked["objects"][0]["disposition"] == "blocked"
    assert blocked["ok"] is False


def test_inspector_edits_accessibility_and_shows_delivery_statuses() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(390, 844)
    document, row = add_ui_object(
        document,
        kind="button",
        name="Continue",
        content={"text": "Continue"},
    )
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[dict] = []
    inspector.properties_changed.connect(
        lambda _object_id, changes: emitted.append(changes)
    )

    inspector.accessibility_role_combo.setCurrentIndex(
        inspector.accessibility_role_combo.findData("button")
    )
    inspector.accessibility_label_edit.setText("Continue to payment")
    inspector.focus_order_spin.setValue(3)
    inspector._emit_properties()

    assert emitted[-1]["accessibility"] == {
        "role": "button",
        "label": "Continue to payment",
        "focus_order": 3,
    }
    assert inspector.delivery_status_labels["design_handoff"].text().endswith(
        "Native"
    )
    assert inspector.delivery_status_labels["unreal_umg"].text().endswith(
        "Native"
    )
    assert row["id"] == document["selection"]["object_id"]
    inspector.deleteLater()
    app.processEvents()


def test_accessibility_changes_use_action_and_undo_path() -> None:
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
    row = dialog._painter_ui_document["objects"][-1]
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.object.update",
        {
            "object_id": row["id"],
            "changes": {
                "accessibility": {
                    "role": "button",
                    "label": "Confirm purchase",
                    "focus_order": 4,
                }
            },
        },
    ).to_dict()

    assert result["ok"] is True
    changed = result["result"]["ui_design"]["document"]["objects"][-1]
    assert changed["accessibility"]["label"] == "Confirm purchase"
    dialog._undo()
    restored = dialog._painter_ui_document["objects"][-1]
    assert restored["accessibility"]["label"] == ""
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
