from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "qa_corpus" / "painter_ui_figma_plugins" / "official_ui_samples.json"
OFFICIAL = ROOT / "external" / "tools" / "figma-plugin-samples"


@pytest.mark.skipif(not OFFICIAL.is_dir(), reason="official Figma plugin sample checkout unavailable")
def test_official_figma_plugin_ui_corpus_matches_supported_and_blocked_contract(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_plugin_official_ui_corpus import run_corpus

    report = run_corpus(MANIFEST, tmp_path / "report")
    assert report["passed"] is True
    assert report["case_count"] == 3
    assert report["passed_count"] == 3
