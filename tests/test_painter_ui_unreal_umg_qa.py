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
    reopen = _reopen_script(
        asset_path,
        tmp_path / "reopen.json",
        ["/Game/TigerStudio/Generated/Test/Materials/M_TS_Gradient.M_TS_Gradient"],
        ["Gradient"],
        [3],
    )
    assert "unreal.load_asset" in reopen
    assert "asset.generated_class()" in reopen
    assert "widget_tree_not_exposed_to_python_after_reopen" in reopen
    assert '"generated_class_loaded"' in reopen
    assert "get_material_expressions" in reopen
    assert "MaterialExpressionCustom" in reopen
    assert 'get_editor_property("material_domain")' in reopen
    assert 'get_editor_property("resource_object")' in reopen
    assert 'logical_widget_name + "_Visual"' in reopen
    assert "expected_widget_classes" in reopen
    assert "find_package_referencers_for_asset" in reopen
    assert '"expected_expression_count"' in reopen
    assert 'texture_row["class"] == "Texture2D"' in reopen
    assert '"textures": textures' in reopen

    opened = _open_asset_script(asset_path, tmp_path / "ready.txt")
    assert "unreal.AssetEditorSubsystem" in opened
    assert "open_editor_for_assets" in opened
    assert "ready.txt" in opened


def test_painter_umg_qa_authors_non_default_canvas_anchor_contract() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from tools.qa_painter_ui_unreal_umg import _anchor_qa_document

    document, _report = instantiate_ui_template("mobile_onboarding")
    _document, expectations = _anchor_qa_document(document)
    exported = painter_ui_to_umg_document(_document)
    assert not [
        row for row in exported["Layers"]
        if row["Disposition"] == "Blocked"
    ]
    by_name = {row["name"]: row for row in expectations}

    assert set(by_name) == {
        "Primary CTA",
        "Feature Card A",
        "Feature Card B",
        "Hero Media",
        "UMG Auto Row",
        "UMG Auto First",
        "UMG Auto Second",
        "UMG Auto Grid",
        "UMG Grid Span",
        "UMG Grid Last",
        "UMG Scroll Frame",
        "UMG Scroll Content",
        "UMG Scroll Fixed",
    }
    assert by_name["Primary CTA"]["canvas_slot"]["AnchorMinimum"] == {
        "X": 1.0,
        "Y": 1.0,
    }
    assert by_name["Primary CTA"]["render_transform_pivot"] == {
        "X": 0.25,
        "Y": 0.75,
    }
    assert by_name["Primary CTA"]["disposition"] == "Native"
    assert by_name["Primary CTA"]["asset_id"]
    assert by_name["Primary CTA"]["image_fill"]["AssetId"] == (
        by_name["Primary CTA"]["asset_id"]
    )
    assert by_name["Primary CTA"]["image_fill"]["Mode"] == "Fill"
    assert by_name["Primary CTA"]["image_fill"]["FocalPoint"] == {
        "X": 0.62,
        "Y": 0.48,
    }
    assert any(
        row["Id"] == by_name["Primary CTA"]["asset_id"]
        and row["Kind"] == "texture"
        for row in exported["Resources"]
    )
    assert by_name["Feature Card A"]["canvas_slot"]["AnchorMaximum"][
        "X"
    ] == 1.0
    scale_slot = by_name["Feature Card B"]["canvas_slot"]
    assert scale_slot["AnchorMinimum"] != scale_slot["AnchorMaximum"]
    assert scale_slot["Offsets"] == {
        "Left": 0.0,
        "Top": 0.0,
        "Right": 0.0,
        "Bottom": 0.0,
    }
    custom_slot = by_name["Hero Media"]["canvas_slot"]
    assert custom_slot["AnchorMinimum"] == {"X": 0.2, "Y": 0.3}
    assert custom_slot["AnchorMaximum"] == {"X": 0.2, "Y": 0.3}
    assert by_name["Hero Media"]["render_transform_pivot"] == {
        "X": 0.4,
        "Y": 0.6,
    }
    assert by_name["Hero Media"]["disposition"] == "Material"
    assert by_name["Hero Media"]["material"]["Generator"] == (
        "tiger_ui_rounded_card_sdf_custom_hlsl_v1"
    )
    assert by_name["Hero Media"]["material"]["Kind"] == "RoundedCard"
    assert by_name["Hero Media"]["material"]["FillKind"] == "RadialGradient"
    assert by_name["Hero Media"]["material"]["Width"] == {
        "X": 0.22,
        "Y": 0.94,
    }
    assert by_name["Hero Media"]["material"]["CornerRadii"] == {
        "X": 32.0,
        "Y": 20.0,
        "Z": 28.0,
        "W": 16.0,
    }
    assert by_name["Hero Media"]["material"]["Stroke"]["Alignment"] == (
        "Inside"
    )
    assert by_name["Hero Media"]["material"]["DropShadow"]["Enabled"] is True
    assert by_name["Hero Media"]["material"]["InnerShadow"]["Enabled"] is True
    assert len(by_name["Hero Media"]["material"]["Stops"]) == 3
    assert by_name["UMG Auto Row"]["panel_kind"] == "Horizontal"
    assert by_name["UMG Auto First"]["flow_slot"][
        "VerticalAlignment"
    ] == "Center"
    assert by_name["UMG Auto Grid"]["panel_kind"] == "Grid"
    assert by_name["UMG Grid Span"]["flow_slot"]["ColumnSpan"] == 2
    assert by_name["UMG Scroll Frame"]["scroll_overflow"] == "Both"
    assert by_name["UMG Scroll Fixed"]["scroll_position"] == "Fixed"
