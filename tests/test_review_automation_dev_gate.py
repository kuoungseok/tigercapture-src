from __future__ import annotations

import sys


def test_review_paths_default_to_separate_workspace(tmp_path, monkeypatch):
    from app.review_automation.paths import REVIEW_ROOT_ENV, review_paths

    monkeypatch.delenv(REVIEW_ROOT_ENV, raising=False)
    project_root = tmp_path / "TigerCapture"
    paths = review_paths(project_root=project_root)

    assert paths["root"] == tmp_path / "ReviewAutomationWorkspace"
    assert paths["samples"] == tmp_path / "ReviewAutomationWorkspace" / "samples"
    assert paths["outputs"] == tmp_path / "ReviewAutomationWorkspace" / "outputs"
    assert paths["sample_report"] == tmp_path / "ReviewAutomationWorkspace" / "qa" / "review_sample_resources_qa.json"


def test_review_paths_allow_explicit_external_root(tmp_path, monkeypatch):
    from app.review_automation.paths import REVIEW_ROOT_ENV, review_paths

    custom_root = tmp_path / "PrivateReviewRoot"
    monkeypatch.setenv(REVIEW_ROOT_ENV, str(custom_root))

    assert review_paths(project_root=tmp_path / "Product")["root"] == custom_root


def test_review_automation_dev_gate_requires_source_or_env(tmp_path, monkeypatch):
    from app.review_automation.dev_gate import DEV_ENV_VARS, review_automation_dev_enabled

    for name in DEV_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    assert review_automation_dev_enabled(tmp_path) is False

    (tmp_path / ".git").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "review_automation_launcher.py").write_text("# dev launcher\n", encoding="utf-8")
    assert review_automation_dev_enabled(tmp_path) is True

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert review_automation_dev_enabled(tmp_path) is False

    monkeypatch.setenv("TIGERCAPTURE_REVIEW_AUTOMATION", "1")
    assert review_automation_dev_enabled(tmp_path) is True
