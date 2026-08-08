from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document_with_objects(count: int, *, kind: str = "rectangle"):
    from app.painter_ui_document import create_ui_document

    document = create_ui_document(1440, 900, name="Performance")
    document["objects"] = [
        {
            "id": f"ui-object-{index + 1}",
            "kind": kind,
            "name": f"Object {index + 1}",
            "artboard_id": "artboard-1",
            "parent_id": "",
            "x": float(index % 100),
            "y": float(index // 100),
            "width": 16,
            "height": 16,
        }
        for index in range(count)
    ]
    return document


def test_performance_budget_covers_normal_document() -> None:
    from app.painter_ui_performance_budget import (
        SCHEMA,
        inspect_painter_ui_performance_budget,
    )

    report = inspect_painter_ui_performance_budget(
        _document_with_objects(120)
    )
    assert report["schema"] == SCHEMA
    assert report["status"] == "covered"
    assert report["budget_count"] == 6
    assert report["blocked_count"] == 0
    assert report["policy"]["wall_clock_claim"] == "not_measured"


def test_performance_budget_warns_and_blocks_at_document_scale() -> None:
    from app.painter_ui_performance_budget import (
        inspect_painter_ui_performance_budget,
    )

    warning = inspect_painter_ui_performance_budget(
        _document_with_objects(2000)
    )
    object_warning = next(
        row for row in warning["budgets"] if row["id"] == "objects"
    )
    assert warning["status"] == "warning"
    assert object_warning["status"] == "warning"

    blocked = inspect_painter_ui_performance_budget(
        _document_with_objects(5000)
    )
    object_block = next(
        row for row in blocked["budgets"] if row["id"] == "objects"
    )
    assert blocked["status"] == "blocked"
    assert blocked["ok"] is False
    assert object_block["status"] == "blocked"


def test_performance_budget_counts_images_components_and_interactions() -> None:
    from app.painter_ui_performance_budget import (
        inspect_painter_ui_performance_budget,
    )

    document = _document_with_objects(4)
    document["objects"][0]["kind"] = "image"
    document["objects"][1]["kind"] = "image"
    document["components"] = [
        {"id": "ui-component-1", "name": "Card", "root_object_id": ""}
    ]
    document["interactions"] = [
        {
            "id": "ui-interaction-1",
            "name": "Open",
            "source_object_id": "ui-object-1",
            "trigger": "click",
            "action": "navigate",
            "target_artboard_id": "artboard-1",
        }
    ]
    report = inspect_painter_ui_performance_budget(document)
    rows = {row["id"]: row["value"] for row in report["budgets"]}
    assert rows["images"] == 2
    assert rows["components"] == 1
    assert rows["prototype_transitions"] == 1


def test_performance_budget_does_not_mutate_document() -> None:
    from app.painter_ui_performance_budget import (
        inspect_painter_ui_performance_budget,
    )

    document = _document_with_objects(10)
    before = copy.deepcopy(document)
    inspect_painter_ui_performance_budget(document)
    assert document == before


def test_performance_budget_dialog_has_compact_columns() -> None:
    _app()
    from PySide6.QtWidgets import QPushButton

    from app.painter_i18n import painter_text
    from app.painter_ui_performance_budget import (
        inspect_painter_ui_performance_budget,
    )
    from app.painter_ui_performance_budget_dialog import (
        PainterUIPerformanceBudgetDialog,
    )

    dialog = PainterUIPerformanceBudgetDialog()
    dialog.set_report(
        inspect_painter_ui_performance_budget(_document_with_objects(120))
    )
    assert dialog.tree.topLevelItemCount() == 6
    dialog.resize(420, 500)
    dialog.show()
    _app().processEvents()
    assert dialog.tree.isColumnHidden(2) is True
    assert dialog.tree.isColumnHidden(3) is True

    emitted: list[bool] = []
    dialog.refresh_requested.connect(lambda: emitted.append(True))
    buttons = dialog.findChildren(QPushButton)
    next(
        button
        for button in buttons
        if button.text() == painter_text("Refresh")
    ).click()
    assert emitted == [True]


def test_performance_budget_action_and_quick_action_are_registered() -> None:
    from app.actions.registry import ActionRegistry
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    action = next(
        row
        for row in ActionRegistry(owner=None).list_actions()
        if row["id"] == "paint.ui.performance_budget.inspect"
    )
    assert action["mutating"] is False
    quick = search_painter_ui_quick_actions(
        create_ui_document(390, 844),
        "performance budget",
    )
    row = next(
        item
        for item in quick["results"]
        if item["id"] == "document.performance_budget"
    )
    assert row["operation"] == {"type": "performance_budget"}


def test_performance_budget_action_runs_against_active_document() -> None:
    from app.actions.registry import ActionRegistry

    class _PainterOwner:
        canvas = object()
        _painter_ui_document = _document_with_objects(2000)

        def painter_action_state(self):
            return {}

        def export_png_to_path(self, _path):
            return {}

    result = ActionRegistry(owner=_PainterOwner()).execute(
        "paint.ui.performance_budget.inspect",
        {},
    ).to_dict()
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["status"] == "warning"
