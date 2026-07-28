from __future__ import annotations

import json
from pathlib import Path

from app.unreal_umg_plugin import (
    PLUGIN_NAME,
    PLUGIN_SOURCE_RELATIVE_ROOT,
    bundled_plugin_manifest,
    bundled_plugin_root,
    install_project_plugin,
    plugin_status,
)


def test_bundled_umg_plugin_has_shared_runtime_and_editor_modules() -> None:
    root = bundled_plugin_root()
    manifest = bundled_plugin_manifest()
    modules = {row["Name"]: row["Type"] for row in manifest["Modules"]}
    source_root = Path(__file__).resolve().parents[1] / PLUGIN_SOURCE_RELATIVE_ROOT
    source_manifest = json.loads(
        (source_root / f"{PLUGIN_NAME}.uplugin").read_text(encoding="utf-8")
    )

    assert root.parent.name == "UMG"
    assert PLUGIN_SOURCE_RELATIVE_ROOT.parts[-2:] == ("UMG", PLUGIN_NAME)
    assert manifest["FriendlyName"] == "Tiger Studio UMG"
    assert manifest["VersionName"] == "0.3.0"
    assert source_manifest["EnabledByDefault"] is False
    assert modules == {
        "TigerStudioUMG": "Runtime",
        "TigerStudioUMGEditor": "Editor",
    }
    assert (
        source_root / "Source" / "TigerStudioUMG" / "TigerStudioUMG.Build.cs"
    ).is_file()
    assert (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "TigerStudioUMGEditor.Build.cs"
    ).is_file()
    types = (
        source_root
        / "Source"
        / "TigerStudioUMG"
        / "Public"
        / "TigerStudioUMGTypes.h"
    ).read_text(encoding="utf-8")
    preflight = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "Private"
        / "TigerStudioUMGImportSubsystem.cpp"
    ).read_text(encoding="utf-8")
    assert "int32 SchemaVersion = 4;" in types
    assert "TArray<FString> BlockReasons;" in types
    assert "Result.Document.SchemaVersion != 4" in preflight
    assert "FString::Join(Result.BlockReasons" in preflight
    if "bundled" in root.parts:
        assert not (root / "Source").exists()
        assert not (root / "Intermediate").exists()


def test_project_local_install_enables_plugin_without_engine_install(tmp_path: Path) -> None:
    project = tmp_path / "Demo.uproject"
    project.write_text(
        json.dumps({"FileVersion": 3, "Plugins": [{"Name": "Other", "Enabled": True}]}),
        encoding="utf-8",
    )

    before = plugin_status(project)
    assert before.installed is False
    assert before.enabled is False

    after = install_project_plugin(project)
    payload = json.loads(project.read_text(encoding="utf-8"))
    plugin_rows = {
        row["Name"]: row["Enabled"]
        for row in payload["Plugins"]
        if isinstance(row, dict)
    }

    assert after.installed is True
    assert after.enabled is True
    assert after.update_required is False
    assert plugin_rows["Other"] is True
    assert plugin_rows[PLUGIN_NAME] is True
    assert (
        tmp_path / "Plugins" / PLUGIN_NAME / f"{PLUGIN_NAME}.uplugin"
    ).is_file()
