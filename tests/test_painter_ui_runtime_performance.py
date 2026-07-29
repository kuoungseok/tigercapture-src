from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_runtime_measurement_classifier_has_warning_and_block_gates() -> None:
    from app.painter_ui_runtime_performance import (
        classify_runtime_measurement,
    )

    assert classify_runtime_measurement(9.9, 10.0, 20.0) == "covered"
    assert classify_runtime_measurement(10.0, 10.0, 20.0) == "warning"
    assert classify_runtime_measurement(20.0, 10.0, 20.0) == "blocked"


def test_runtime_performance_runs_real_core_paths() -> None:
    from app.painter_ui_runtime_performance import (
        SCHEMA,
        run_painter_ui_runtime_performance,
    )

    report = run_painter_ui_runtime_performance(
        object_count=25,
        iterations=1,
    )
    assert report["schema"] == SCHEMA
    assert report["object_count"] == 25
    assert report["iterations"] == 1
    assert {row["id"] for row in report["cases"]} == {
        "normalize",
        "responsive",
        "layout_diagnostics",
        "quick_actions",
    }
    assert all(len(row["samples_ms"]) == 1 for row in report["cases"])
    assert report["measurement_policy"]["clock"] == "time.perf_counter"
    assert (
        report["measurement_policy"]["claim_scope"]
        == "local_machine_runtime_only"
    )


def test_runtime_performance_dialog_empty_and_compact_states() -> None:
    _app()
    from PySide6.QtWidgets import QPushButton

    from app.painter_i18n import painter_text
    from app.painter_ui_runtime_performance import (
        run_painter_ui_runtime_performance,
    )
    from app.painter_ui_runtime_performance_dialog import (
        PainterUIRuntimePerformanceDialog,
    )

    dialog = PainterUIRuntimePerformanceDialog()
    assert dialog.tree.topLevelItemCount() == 0
    dialog.set_report(
        run_painter_ui_runtime_performance(
            object_count=25,
            iterations=1,
        )
    )
    assert dialog.tree.topLevelItemCount() == 4
    dialog.resize(420, 500)
    dialog.show()
    _app().processEvents()
    assert dialog.tree.isColumnHidden(2) is True
    assert dialog.tree.isColumnHidden(3) is True

    emitted: list[bool] = []
    dialog.run_requested.connect(lambda: emitted.append(True))
    button = next(
        row
        for row in dialog.findChildren(QPushButton)
        if row.text() == painter_text("Run benchmark")
    )
    button.click()
    assert emitted == [True]


def test_runtime_performance_action_and_quick_action() -> None:
    from app.actions.registry import ActionRegistry
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    action = next(
        row
        for row in ActionRegistry(owner=None).list_actions()
        if row["id"] == "paint.ui.runtime_performance.run"
    )
    assert action["mutating"] is False
    result = ActionRegistry(owner=object()).execute(
        "paint.ui.runtime_performance.run",
        {"object_count": 25, "iterations": 1},
    ).to_dict()
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["case_count"] == 4

    quick = search_painter_ui_quick_actions(
        create_ui_document(390, 844),
        "runtime performance",
    )
    row = next(
        item
        for item in quick["results"]
        if item["id"] == "document.runtime_performance"
    )
    assert row["operation"] == {"type": "runtime_performance"}
