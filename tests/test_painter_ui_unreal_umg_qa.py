from __future__ import annotations

import json
from pathlib import Path


def test_painter_umg_qa_builds_disposable_project(tmp_path: Path) -> None:
    from tools.qa_painter_ui_unreal_umg import _ensure_project

    project = _ensure_project(tmp_path)
    payload = json.loads(project.read_text(encoding="utf-8"))
    assert project.name == "TigerPainterUMGQA.uproject"
    assert payload["EngineAssociation"] == "5.8"
    assert payload["Plugins"] == []


def test_painter_umg_qa_scripts_verify_reopen_and_open_editor(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg import (
        _open_asset_script,
        _reopen_script,
    )

    asset_path = "/Game/TigerStudio/Generated/Test.WBP_Test"
    reopen = _reopen_script(asset_path, tmp_path / "reopen.json")
    assert "unreal.load_asset" in reopen
    assert "asset.generated_class()" in reopen
    assert "widget_tree_not_exposed_to_python_after_reopen" in reopen
    assert '"generated_class_loaded"' in reopen

    opened = _open_asset_script(asset_path, tmp_path / "ready.txt")
    assert "unreal.AssetEditorSubsystem" in opened
    assert "open_editor_for_assets" in opened
    assert "ready.txt" in opened
