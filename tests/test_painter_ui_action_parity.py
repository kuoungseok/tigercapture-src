from __future__ import annotations


def test_action_parity_classifies_live_painter_ui_registry() -> None:
    from app.actions.registry import ActionRegistry
    from app.painter_ui_action_parity import inspect_painter_ui_action_parity

    report = inspect_painter_ui_action_parity(
        ActionRegistry(owner=None).list_actions()
    )
    assert report["action_count"] >= 240
    assert report["missing_action_ids"] == []
    assert report["orphan_candidate_ids"] == []
    assert report["covered_family_count"] == report["family_count"]
    assert report["status"] == "covered"


def test_action_parity_reports_missing_and_unclassified_actions() -> None:
    from app.painter_ui_action_parity import inspect_painter_ui_action_parity

    report = inspect_painter_ui_action_parity(
        [{"id": "paint.ui.unknown.custom", "mutating": False}]
    )
    assert "paint.ui.document.inspect" in report["missing_action_ids"]
    assert report["orphan_candidate_ids"] == ["paint.ui.unknown.custom"]
    assert report["status"] == "blocked"


def test_action_parity_action_and_quick_action_are_read_only() -> None:
    from app.actions.registry import ActionRegistry
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    result = ActionRegistry(owner=object()).execute(
        "paint.ui.action_parity.inspect", {}
    ).to_dict()
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["status"] == "covered"
    quick = search_painter_ui_quick_actions(
        create_ui_document(390, 844), "action parity"
    )
    row = next(
        item
        for item in quick["results"]
        if item["id"] == "document.action_parity"
    )
    assert row["operation"] == {"type": "action_parity"}
