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
    _app()
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
        "canvas_initial_load",
        "pan_zoom",
        "selection_refresh",
        "viewport_resize",
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
    assert dialog.tree.topLevelItemCount() == 8
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
    _app()
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
    assert result["result"]["case_count"] == 8

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


def test_workspace_reuses_resolved_layout_for_selection_only_changes() -> None:
    _app()
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(390, 844),
        kind="rectangle",
        x=40,
        y=60,
        width=120,
        height=80,
    )
    overlay = PainterUIDesignOverlay()
    overlay.set_document(document)
    resolved = overlay._resolved_geometry

    overlay.set_document(select_ui_object(document, row["id"]))

    assert overlay._resolved_geometry is resolved
    assert overlay._effective_document["selection"]["object_id"] == row["id"]


def test_workspace_render_cache_rebuilds_for_same_revision_content() -> None:
    _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    first, _first_row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=100,
        y=100,
        width=200,
        height=120,
    )
    second, second_row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=300,
        y=200,
        width=120,
        height=80,
    )
    assert first["document_id"] == second["document_id"]
    assert first["revision"] == second["revision"]

    overlay = PainterUIDesignOverlay()
    overlay.set_document(first)
    resolved = overlay._resolved_geometry
    overlay.set_document(second)

    assert overlay._resolved_geometry is not resolved
    assert overlay._resolved_geometry[second_row["id"]]["x"] == 300.0


def test_workspace_render_cache_indexes_mask_targets() -> None:
    _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_masks import create_ui_mask
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, mask_row = add_ui_object(
        create_ui_document(390, 844),
        kind="ellipse",
        x=20,
        y=20,
        width=100,
        height=100,
    )
    document, target_row = add_ui_object(
        document,
        kind="rectangle",
        x=20,
        y=20,
        width=160,
        height=100,
    )
    document, _mask = create_ui_mask(
        document,
        mask_row["id"],
        target_ids=[target_row["id"]],
    )

    overlay = PainterUIDesignOverlay()
    overlay.set_document(document)
    source = overlay._mask_source_for_target(target_row["id"])

    assert source is not None
    assert source[0]["id"] == mask_row["id"]
