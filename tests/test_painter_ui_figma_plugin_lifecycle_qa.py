from pathlib import Path


def test_fp3_webview_lifecycle_is_visible_and_bounded(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_plugin_lifecycle import run_lifecycle_qa

    report = run_lifecycle_qa(tmp_path / "lifecycle")
    assert report["passed"] is True
    assert report["initial_size"] == [360, 220]
    assert report["resized_size"] == [560, 300]
    assert report["hidden"] is True
    assert report["restored"] is True
    assert report["closed"] is True
