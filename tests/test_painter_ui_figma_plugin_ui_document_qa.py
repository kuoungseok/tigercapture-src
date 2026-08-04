from pathlib import Path


def test_fp3_manager_ui_document_changes_use_one_real_painter_undo(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_plugin_ui_document import run_ui_document_qa

    report = run_ui_document_qa(tmp_path / "ui_document")
    assert report["passed"] is True
    assert report["object_names"] == ["UI Plugin card"]
    assert report["undo_labels"] == ["Run Figma UI plugin"]
    assert report["object_count_after_undo"] == 0
