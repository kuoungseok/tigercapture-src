from pathlib import Path


def test_fp3_webview_allows_only_the_approved_manifest_domain(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_plugin_network import run_network_qa

    report = run_network_qa(tmp_path / "network")
    assert report["passed"] is True
    assert report["status"] == "허용 OK / 미승인 차단 OK"
