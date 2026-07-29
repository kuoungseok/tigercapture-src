from __future__ import annotations

import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_release_corpus_round_trips_all_packages(tmp_path: Path) -> None:
    from app.painter_ui_release_corpus import (
        SCHEMA,
        run_painter_ui_release_corpus,
    )

    report = run_painter_ui_release_corpus(tmp_path / "release")

    assert report["schema"] == SCHEMA
    assert report["ok"] is True
    assert report["case_count"] == 7
    assert report["passed_count"] == 7
    assert report["blocked_count"] == 0
    assert Path(report["report_path"]).is_file()
    assert {row["id"] for row in report["cases"]} == {
        "native_tspaint",
        "figma_exchange",
        "template_package",
        "design_handoff",
        "prototype_package",
        "review_package",
        "umg_contract",
    }

    semantic_cases = {
        "native_tspaint",
        "figma_exchange",
        "template_package",
        "design_handoff",
        "prototype_package",
        "review_package",
    }
    for row in report["cases"]:
        if row["id"] in semantic_cases:
            assert row["detail"]["expected_sha256"]
            assert (
                row["detail"]["expected_sha256"]
                == row["detail"]["actual_sha256"]
            )


def test_release_corpus_fixture_is_deterministic() -> None:
    from app.painter_ui_release_corpus import (
        build_painter_ui_release_document,
    )

    assert (
        build_painter_ui_release_document()
        == build_painter_ui_release_document()
    )


def test_release_corpus_reports_honest_external_runtime_gates(
    tmp_path: Path,
) -> None:
    from app.painter_ui_release_corpus import run_painter_ui_release_corpus

    report = run_painter_ui_release_corpus(tmp_path / "release")
    claims = report["runtime_claims"]
    assert claims["figma_native_file"] == "not_claimed"
    assert claims["unreal_widget_blueprint_compile"] == "not_run"
    assert claims["unreal_real_capture"] == "not_run"

    umg = next(row for row in report["cases"] if row["id"] == "umg_contract")
    assert umg["detail"]["scope"] == "provider_neutral_contract_only"
    assert umg["detail"]["unreal_compile_and_capture"] == "not_run"


def test_release_corpus_dialog_empty_report_and_compact_columns(
    tmp_path: Path,
) -> None:
    _app()
    from app.painter_ui_release_corpus import run_painter_ui_release_corpus
    from app.painter_ui_release_corpus_dialog import (
        PainterUIReleaseCorpusDialog,
    )

    dialog = PainterUIReleaseCorpusDialog()
    assert dialog.tree.topLevelItemCount() == 0
    assert dialog.open_button.isEnabled() is False

    report = run_painter_ui_release_corpus(tmp_path / "release")
    dialog.set_report(report)
    assert dialog.tree.topLevelItemCount() == 7
    assert dialog.open_button.isEnabled() is True

    dialog.resize(420, 520)
    dialog.show()
    _app().processEvents()
    assert dialog.tree.isColumnHidden(2) is True
    assert dialog.tree.isColumnHidden(3) is True

    emitted: list[bool] = []
    dialog.run_requested.connect(lambda: emitted.append(True))
    dialog.run_button.click()
    assert emitted == [True]


def test_release_corpus_action_is_registered_read_only() -> None:
    from app.actions.registry import ActionRegistry

    registry = ActionRegistry(owner=None)
    action = next(
        row
        for row in registry.list_actions()
        if row["id"] == "paint.ui.release_corpus.run"
    )
    assert action["mutating"] is False


def test_release_corpus_action_runs_same_service(tmp_path: Path) -> None:
    from app.actions.registry import ActionRegistry

    result = ActionRegistry(owner=object()).execute(
        "paint.ui.release_corpus.run",
        {"output_dir": str(tmp_path / "action_release")},
    ).to_dict()
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["passed_count"] == 7


def test_release_corpus_is_discoverable_from_quick_actions() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    result = search_painter_ui_quick_actions(
        create_ui_document(390, 844),
        "release corpus",
    )
    row = next(
        item
        for item in result["results"]
        if item["id"] == "document.release_corpus"
    )
    assert row["operation"] == {"type": "release_corpus"}
