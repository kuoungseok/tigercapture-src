from pathlib import Path


def test_figma_plugin_manager_product_success_failure_and_undo(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_plugin_product import run_product_qa

    report = run_product_qa(tmp_path / "product_qa")

    assert report["passed"] is True
    assert report["success"]["created_count"] == 1
    assert report["success"]["object_count_after_undo"] == 0
    assert report["failure"]["document_unchanged"] is True
    assert report["failure"]["status_state"] == "error"
