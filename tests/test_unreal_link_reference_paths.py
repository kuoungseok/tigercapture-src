from __future__ import annotations

from app.unreal_link_reference_paths import (
    DEFAULT_UASSET_INSPECTOR_ROOT,
    DEFAULT_UE_ENGINE_ROOT,
    UASSET_INSPECTOR_ENV,
    UE_ENGINE_ENV,
    format_unreal_link_reference_report,
    unreal_link_reference_report,
    unreal_link_reference_roots,
)


def test_unreal_link_reference_defaults_are_registered_for_ai_development() -> None:
    roots = unreal_link_reference_roots()

    assert roots["uasset_inspector"].path == DEFAULT_UASSET_INSPECTOR_ROOT
    assert roots["ue_58"].path == DEFAULT_UE_ENGINE_ROOT
    assert DEFAULT_UASSET_INSPECTOR_ROOT.as_posix() == "D:/Pupg_workspace/ToolsStandalone/UAssetInspector"
    assert DEFAULT_UE_ENGINE_ROOT.as_posix() == "D:/UE_5.8"
    assert "UAssetInspector.sln" in roots["uasset_inspector"].required_children
    assert "Engine/Binaries/Win64/UnrealEditor.exe" in roots["ue_58"].required_children


def test_unreal_link_reference_env_overrides(monkeypatch, tmp_path) -> None:
    custom_tool = tmp_path / "tool"
    custom_engine = tmp_path / "engine"
    monkeypatch.setenv(UASSET_INSPECTOR_ENV, str(custom_tool))
    monkeypatch.setenv(UE_ENGINE_ENV, str(custom_engine))

    roots = unreal_link_reference_roots()

    assert roots["uasset_inspector"].path == custom_tool
    assert roots["ue_58"].path == custom_engine


def test_unreal_link_reference_report_is_human_readable() -> None:
    report = unreal_link_reference_report()
    text = format_unreal_link_reference_report()

    assert "Do not copy" in report["note"]
    assert "D:/UE_5.8" in text
    assert UASSET_INSPECTOR_ENV in text
    assert UE_ENGINE_ENV in text
