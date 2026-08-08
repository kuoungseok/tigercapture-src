from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_ai_prototype_plan_previews_editable_interactions_and_applies() -> None:
    from app.painter_ui_ai_prototype import (
        AI_PROTOTYPE_APPLY_SCHEMA,
        AI_PROTOTYPE_PLAN_SCHEMA,
        apply_ui_prototype_build,
        plan_ui_prototype_build,
    )
    from app.painter_ui_document import create_ui_document

    document = create_ui_document(390, 844)
    plan = plan_ui_prototype_build(
        document,
        prompt="Create a mobile onboarding screen with an interactive button",
    )

    assert plan["schema"] == AI_PROTOTYPE_PLAN_SCHEMA
    assert plan["requires_explicit_apply"] is True
    assert plan["interaction_specs"]
    assert plan["preview_document"]["interactions"]
    assert plan["prototype"]["ok"] is True
    assert plan["delivery"]["schema"] == (
        "tigerstudio.painter.ui.advanced_delivery.v1"
    )
    assert set(plan["delivery"]["targets"]) == {"web", "app", "umg"}
    assert plan["preview_diff"]["change_count"] > 0

    updated, report = apply_ui_prototype_build(document, plan)

    assert report["schema"] == AI_PROTOTYPE_APPLY_SCHEMA
    assert report["added_interaction_ids"]
    assert report["prototype"]["ok"] is True
    assert report["delivery"]["ok"] is True
    assert len(updated["interactions"]) >= len(report["added_interaction_ids"])


def test_ai_prototype_plan_rejects_stale_and_required_operation_omission() -> None:
    from app.painter_ui_ai_prototype import (
        apply_ui_prototype_build,
        plan_ui_prototype_build,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844)
    plan = plan_ui_prototype_build(
        document,
        prompt="Create an interactive dashboard",
    )
    changed, _row = add_ui_object(document, kind="rectangle")

    with pytest.raises(ValueError, match="stale"):
        apply_ui_prototype_build(changed, plan)
    with pytest.raises(ValueError, match="build-editable-ui"):
        apply_ui_prototype_build(
            document,
            plan,
            selected_operation_ids=["wire-prototype"],
        )


def test_advanced_delivery_reports_web_app_umg_dispositions() -> None:
    from app.painter_ui_advanced_delivery import (
        inspect_advanced_ui_delivery,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(390, 844)
    document, _rectangle = add_ui_object(document, kind="rectangle")
    document, _path = add_ui_object(document, kind="path")
    document, _actor = add_ui_object(document, kind="motion_actor")
    document, painted = add_ui_object(document, kind="ellipse")
    document, _painted = update_ui_object(
        document,
        painted["id"],
        {"style": {**painted["style"], "paint_layer_id": "paint-layer-1"}},
    )

    report = inspect_advanced_ui_delivery(document)

    assert report["schema"] == "tigerstudio.painter.ui.advanced_delivery.v1"
    assert report["ok"] is True
    assert report["targets"]["web"]["counts"]["Native"] >= 1
    assert report["targets"]["web"]["counts"]["Vector"] >= 1
    assert report["targets"]["web"]["counts"]["Baked"] >= 1
    assert report["targets"]["web"]["counts"]["Actor Only"] >= 1
    assert report["targets"]["umg"]["counts"]["Material"] >= 1


def test_production_panel_routes_interactive_prototype_mode() -> None:
    app = _app()
    from app.painter_ui_ai_prototype import plan_ui_prototype_build
    from app.painter_ui_document import create_ui_document
    from app.painter_i18n import painter_text
    from app.painter_ui_production_panel import PainterUIProductionPanel

    panel = PainterUIProductionPanel()
    panel.set_document(create_ui_document(390, 844))
    panel.ai_mode_combo.setCurrentIndex(
        panel.ai_mode_combo.findData("prototype")
    )
    panel.ai_prompt_edit.setText("Create an interactive mobile screen")
    planned: list[str] = []
    applied: list[object] = []
    panel.ai_prototype_plan_requested.connect(planned.append)
    panel.ai_prototype_apply_requested.connect(applied.append)

    panel._request_ai_plan()
    assert planned == ["Create an interactive mobile screen"]

    plan = plan_ui_prototype_build(
        panel._document,
        prompt=planned[0],
    )
    panel.set_ai_plan(plan)
    panel._request_ai_apply()
    app.processEvents()

    assert applied == [plan]
    assert painter_text("Explicit apply required") in panel.ai_summary.text()
    assert "WEB" in panel.ai_delivery_label.text()
    assert painter_text("Ready") in panel.ai_delivery_label.text()


def test_ai_prototype_actions_share_document_and_undo() -> None:
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
        "paint.ui.ai.prototype.plan",
        "paint.ui.ai.prototype.apply",
        "paint.ui.advanced_delivery.inspect",
    }.issubset(action_ids)

    before_revision = dialog._painter_ui_document["revision"]
    before_interactions = list(dialog._painter_ui_document["interactions"])
    planned = registry.execute(
        "paint.ui.ai.prototype.plan",
        {"prompt": "Create an interactive mobile onboarding screen"},
    ).to_dict()
    assert planned["ok"] is True
    applied = registry.execute(
        "paint.ui.ai.prototype.apply",
        {"plan": planned["result"]},
    ).to_dict()
    assert applied["ok"] is True
    assert dialog._painter_ui_document["interactions"]
    delivery = registry.execute(
        "paint.ui.advanced_delivery.inspect",
        {},
    ).to_dict()
    assert delivery["ok"] is True
    assert set(delivery["result"]["targets"]) == {"web", "app", "umg"}

    undone = registry.execute("paint.history.undo", {}).to_dict()
    assert undone["ok"] is True
    assert dialog._painter_ui_document["revision"] == before_revision
    assert dialog._painter_ui_document["interactions"] == before_interactions
    dialog.close()
