from __future__ import annotations

from pathlib import Path

import pytest


def test_official_figma_sample_corpus_runs_when_checkout_is_available(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "external" / "tools" / "figma-plugin-samples"
    if not source.is_dir():
        pytest.skip("official figma/plugin-samples checkout is not installed")
    from tools.qa_painter_ui_figma_plugin_official_corpus import run_corpus

    report = run_corpus(
        root / "qa_corpus" / "painter_ui_figma_plugins" / "official_samples.json",
        tmp_path,
    )

    assert report["case_count"] == 3
    assert report["passed_count"] == 3
    assert report["passed"] is True
