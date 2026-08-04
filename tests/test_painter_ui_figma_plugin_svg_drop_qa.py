from pathlib import Path


def test_official_svg_drop_creates_real_painter_hierarchy_and_one_undo(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_plugin_svg_drop import run_svg_drop_qa

    report = run_svg_drop_qa(tmp_path / "svg_drop")
    assert report["passed"] is True
    assert [row["kind"] for row in report["hierarchy"]] == ["frame", "path"]
    assert report["hierarchy"][1]["parent_id"] == report["hierarchy"][0]["id"]
    assert report["undo_labels"] == ["Run Figma UI plugin"]
    assert report["object_count_after_undo"] == 0
