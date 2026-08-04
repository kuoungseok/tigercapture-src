from pathlib import Path


def test_fp3_webview_disables_and_terminates_a_timed_out_plugin(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_plugin_recovery import run_recovery_qa

    report = run_recovery_qa(tmp_path / "recovery")
    assert report["passed"] is True
    assert report["view_enabled"] is False
    assert report["worker_stopped"] is True
