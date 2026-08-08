from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_painter_umg_qa_builds_disposable_project(tmp_path: Path) -> None:
    from tools.qa_painter_ui_unreal_umg import _ensure_project

    project = _ensure_project(tmp_path)
    payload = json.loads(project.read_text(encoding="utf-8"))
    assert project.name == "TigerPainterUMGQA.uproject"
    assert payload["EngineAssociation"] == "5.8"
    assert payload["Plugins"] == []


def test_painter_umg_qa_template_cli_keeps_layout_fixture_opt_in() -> None:
    from tools.qa_painter_ui_unreal_umg import _argument_parser

    default_args = _argument_parser().parse_args([])
    assert default_args.template == "mobile_onboarding"
    assert default_args.artboard_id == ""
    assert default_args.umg_layout_qa is False

    dashboard_args = _argument_parser().parse_args(
        [
            "--template",
            "saas_dashboard",
            "--artboard-id",
            "artboard-2",
            "--umg-layout-qa",
        ]
    )
    assert dashboard_args.template == "saas_dashboard"
    assert dashboard_args.artboard_id == "artboard-2"
    assert dashboard_args.umg_layout_qa is True


def test_painter_umg_qa_activates_and_reports_requested_artboard() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from tools.qa_painter_ui_unreal_umg import _activate_template_artboard

    source, _report = instantiate_ui_template("saas_dashboard")
    selected, artboard = _activate_template_artboard(source, "artboard-2")

    assert source["active_artboard_id"] == "artboard-1"
    assert selected["active_artboard_id"] == "artboard-2"
    assert artboard == {
        "id": "artboard-2",
        "name": "Mobile",
        "index": 1,
        "width": 390.0,
        "height": 844.0,
        "is_default": False,
    }
    with pytest.raises(ValueError, match="Available artboards"):
        _activate_template_artboard(source, "missing-artboard")


def test_painter_umg_qa_prepares_original_saas_template_for_real_ue() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from tools.qa_painter_ui_unreal_umg import (
        _prepare_builtin_template_qa_document,
        _umg_document_expectations,
    )

    source, _template_report = instantiate_ui_template("saas_dashboard")
    prepared, preparation = _prepare_builtin_template_qa_document(source)
    _exported, expectations = _umg_document_expectations(prepared)

    # Visual/object authoring data is the compatibility input. Only prototype
    # routing is excluded from this render-focused real-engine acceptance.
    assert prepared["objects"] == source["objects"]
    assert source["interactions"]
    assert prepared["interactions"] == []
    assert preparation["substitutions"] == []
    assert preparation["excluded_interactions"][0]["action"] == "navigate"
    assert preparation["source"]["blocked_layers"] == []
    assert preparation["source"]["preflight_blockers"] == [
        {
            "object_id": "ui-object-1-button",
            "name": "Primary action",
            "reasons": ["figma_navigation_requires_umg_screen_router"],
        }
    ]

    assert preparation["prepared"]["preflight_ok"] is True
    assert preparation["prepared"]["blocked_layers"] == []
    assert preparation["prepared"]["preflight_blockers"] == []
    assert expectations["active_artboard_id"] == "artboard-1"
    assert expectations["authored_object_count"] == 9
    assert expectations["expected_layer_count"] == 10
    assert expectations["expected_widget_count"] == 10
    assert expectations["disposition_counts"] == {
        "Native": 6,
        "Material": 4,
        "Baked": 0,
        "Blocked": 0,
    }
    assert expectations["expected_material_count"] == 4
    assert {
        row["name"] for row in expectations["material_layers"]
    } == {
        "Metric Card 1",
        "Metric Card 2",
        "Metric Card 3",
        "Chart Region",
    }
    assert {
        row["generator"] for row in expectations["material_layers"]
    } == {"tiger_ui_rounded_card_sdf_custom_hlsl_v1"}


def test_painter_umg_qa_counts_component_definition_materials() -> None:
    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_document import add_ui_object, create_ui_document
    from tools.qa_painter_ui_unreal_umg import _umg_document_expectations

    document, root = add_ui_object(
        create_ui_document(640, 360),
        kind="rectangle",
        name="Component Rounded Surface",
        width=180,
        height=72,
        style={"fill": "#336699FF", "radius": 18},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Rounded Surface Component",
    )

    exported, expectations = _umg_document_expectations(document)

    placement = next(
        row for row in exported["Layers"] if row["Id"] == root["id"]
    )
    assert placement["Disposition"] == "Native"
    assert placement["Material"] == {}
    assert expectations["expected_material_count"] == 1
    assert expectations["material_layers"] == [
        {
            "id": root["id"],
            "name": "Component Rounded Surface",
            "component_id": component["id"],
            "generator": "tiger_ui_rounded_card_sdf_custom_hlsl_v1",
            "stop_count": 2,
        }
    ]


def test_painter_umg_qa_summary_reports_counts_blockers_and_paths() -> None:
    from tools.qa_painter_ui_unreal_umg import _build_qa_summary

    summary = _build_qa_summary(
        preparation={
            "source": {
                "blocked_layers": [
                    {
                        "id": "card-a",
                        "name": "Card A",
                        "kind": "Frame",
                        "reasons": ["unsupported_source_appearance"],
                    }
                ]
            }
        },
        expectations={
            "expected_layer_count": 10,
            "expected_widget_count": 10,
            "expected_material_count": 1,
            "blocked_layers": [],
        },
        generation={
            "ok": True,
            "generated_widget_count": 10,
            "generated_asset_path": "/Game/Tiger/WBP_SaaS.WBP_SaaS",
            "generated_material_paths": [
                "/Game/Tiger/M_SaaS_Card.M_SaaS_Card"
            ],
        },
        reopened={
            "ok": True,
            "materials": [{"ok": True}],
            "material_brushes": [{"ok": True}],
        },
        widget_render={
            "ok": True,
            "output_path": "C:/qa/saas.png",
        },
    )

    assert summary == {
        "generation_status": "passed",
        "reopen_status": "passed",
        "fwidget_renderer_status": "passed",
        "expected_layer_count": 10,
        "expected_widget_count": 10,
        "actual_generated_widget_count": 10,
        "expected_material_count": 1,
        "actual_generated_material_count": 1,
        "generated_material_paths": [
            "/Game/Tiger/M_SaaS_Card.M_SaaS_Card"
        ],
        "reopened_material_count": 1,
        "material_brush_reference_count": 1,
        "material_reopen_ok": True,
        "blocked_layers": [
            {
                "id": "card-a",
                "name": "Card A",
                "kind": "Frame",
                "reasons": ["unsupported_source_appearance"],
            }
        ],
        "source_preflight_blockers": [],
        "prepared_blocked_layers": [],
        "actual_asset_path": "/Game/Tiger/WBP_SaaS.WBP_SaaS",
        "output_path": "C:/qa/saas.png",
    }


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
        material_owner_asset_paths=[
            "/Game/TigerStudio/Generated/Test/Components/WBP_Card.WBP_Card"
        ],
        texture_owner_asset_paths=[
            "/Game/TigerStudio/Generated/Test/Components/WBP_Image.WBP_Image"
        ],
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
    assert "material_owner_asset_paths" in reopen
    assert "texture_owner_asset_paths" in reopen
    assert '"expected_owner_package"' in reopen
    assert "WBP_Card.WBP_Card" in reopen
    assert "WBP_Image.WBP_Image" in reopen
    assert '"expected_expression_count"' in reopen
    assert 'texture_row["class"] == "Texture2D"' in reopen
    assert '"textures": textures' in reopen

    opened = _open_asset_script(asset_path, tmp_path / "ready.txt")
    assert "unreal.AssetEditorSubsystem" in opened
    assert "open_editor_for_assets" in opened
    assert "ready.txt" in opened


def test_painter_umg_qa_resolves_reopen_resource_owner_assets() -> None:
    from tools.qa_painter_ui_unreal_umg import _reopen_owner_asset_paths

    root_asset = "/Game/QA/WBP_Root.WBP_Root"
    component_asset = "/Game/QA/Components/WBP_Switch.WBP_Switch"
    owners = _reopen_owner_asset_paths(
        root_asset,
        {"component-switch": component_asset},
        [
            {"id": "root-gradient", "component_id": ""},
            {"id": "switch-track", "component_id": "component-switch"},
            {"id": "unknown", "component_id": "component-missing"},
        ],
    )

    assert owners == [root_asset, component_asset, root_asset]


def test_painter_umg_qa_internal_renderer_rejects_black_frames(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from tools.qa_painter_ui_unreal_umg import (
        _capture_has_visible_content,
        _capture_pixel_evidence,
        _capture_render_color_evidence,
        _compare_normalized_crop_render,
        _render_widget_script,
    )

    black = tmp_path / "black.png"
    visible = tmp_path / "visible.png"
    Image.new("RGBA", (16, 16), (0, 0, 0, 255)).save(black)
    image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    image.putpixel((8, 8), (255, 120, 32, 255))
    image.save(visible)

    assert _capture_has_visible_content(black) is False
    assert _capture_has_visible_content(visible) is True
    evidence = _capture_pixel_evidence(visible)
    assert evidence["visible_content"] is True
    assert evidence["alpha_bbox"] == [8, 8, 9, 9]
    color_evidence = _capture_render_color_evidence(
        visible,
        [
            {
                "name": "visible_pixel",
                "x": 8,
                "y": 8,
                "rgba": [255, 120, 32, 255],
            }
        ],
    )
    assert color_evidence["ok"] is True
    assert color_evidence["samples"][0]["max_channel_error"] == 0
    wrong_color = _capture_render_color_evidence(
        visible,
        [
            {
                "name": "wrong_pixel",
                "x": 8,
                "y": 8,
                "rgba": [0, 120, 32, 255],
            }
        ],
    )
    assert wrong_color["ok"] is False

    script = _render_widget_script(
        "/Game/TigerStudio/Generated/Test.WBP_Test",
        visible,
        tmp_path / "report.json",
        width=390,
        height=844,
    )
    assert "render_widget_blueprint_to_png" in script
    assert "unreal.Vector2D(390, 844)" in script
    assert '"component_instance_audit"' in script
    assert '"ComponentInstanceAudit"' in script
    assert '"rounded_card_size_audit"' in script
    assert '"RoundedCardSizeAudit"' in script
    assert '"rounded_card_visual_slot_audit"' in script
    assert '"RoundedCardVisualSlotAudit"' in script

    crop_source = Image.new("RGB", (32, 24))
    for y in range(crop_source.height):
        for x in range(crop_source.width):
            crop_source.putpixel(
                (x, y),
                ((x * 17) % 256, (y * 29) % 256, ((x + y) * 11) % 256),
            )
    crop_source_path = tmp_path / "source.png"
    crop_actual_path = tmp_path / "actual.png"
    crop_source.save(crop_source_path)
    crop_source.crop((8, 6, 24, 18)).resize(
        (20, 12),
        Image.Resampling.BILINEAR,
    ).save(crop_actual_path)
    comparison = _compare_normalized_crop_render(
        crop_actual_path,
        crop_source_path,
        tmp_path / "expected.png",
        crop_x=0.25,
        crop_y=0.25,
        crop_width=0.5,
        crop_height=0.5,
    )
    assert comparison["ok"] is True
    assert comparison["luminance_correlation"] > 0.999
    assert comparison["rgb_mae"] < 0.001


def test_painter_umg_qa_authors_non_default_canvas_anchor_contract() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from tools.qa_painter_ui_unreal_umg import _anchor_qa_document

    document, _report = instantiate_ui_template("mobile_onboarding")
    _document, expectations = _anchor_qa_document(document)
    exported = painter_ui_to_umg_document(_document)
    assert _document["interactions"] == []
    assert exported["Interactions"] == []
    active_artboard_id = str(_document["active_artboard_id"])
    authored_widget_count = sum(
        1
        for row in _document["objects"]
        if str(row.get("artboard_id") or "") == active_artboard_id
    )
    assert len(exported["Layers"]) == authored_widget_count + 1
    assert exported["Layers"][0]["Id"] == "__tiger_artboard_background"
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
        "UMG Overlay Stack",
        "UMG Overlay Bottom",
        "UMG Overlay Top",
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
    assert by_name["Primary CTA"]["asset_id"] == ""
    assert by_name["Primary CTA"]["image_fill"] == {}
    component_cta = next(
        row
        for component in exported["Components"]
        for row in component["Layers"]
        if row["Name"] == "Primary CTA"
    )
    assert component_cta["AssetId"]
    assert component_cta["ImageFill"]["AssetId"] == component_cta["AssetId"]
    assert component_cta["ImageFill"]["Mode"] == "Crop"
    assert component_cta["ImageFill"]["Crop"] == {
        "Enabled": True,
        "Units": "Normalized",
        "X": 0.2,
        "Y": 0.15,
        "Width": 0.6,
        "Height": 0.7,
    }
    assert any(
        row["Id"] == component_cta["AssetId"]
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
    assert by_name["UMG Auto Row"]["spacing_strategy"] == "Spacer"
    assert by_name["UMG Auto Row"]["spacer_size_rule"] == "Fill"
    assert by_name["UMG Auto Row"]["spacer_fill_coefficient"] == 1.0
    assert by_name["UMG Auto First"]["flow_slot"][
        "VerticalAlignment"
    ] == "Center"
    assert by_name["UMG Overlay Stack"]["panel_kind"] == "Overlay"
    assert by_name["UMG Overlay Stack"]["spacing_strategy"] == "Padding"
    assert by_name["UMG Overlay Bottom"]["flow_slot"] == {
        "Padding": {"Left": 0.0, "Top": 0.0, "Right": 0.0, "Bottom": 0.0},
        "HorizontalAlignment": "Left",
        "VerticalAlignment": "Top",
        "SizeRule": "Auto",
        "FillCoefficient": 1.0,
    }
    assert by_name["UMG Overlay Top"]["flow_slot"] == {
        "Padding": {"Left": 56.0, "Top": 12.0, "Right": 0.0, "Bottom": 0.0},
        "HorizontalAlignment": "Left",
        "VerticalAlignment": "Top",
        "SizeRule": "Auto",
        "FillCoefficient": 1.0,
    }
    assert by_name["UMG Auto Grid"]["panel_kind"] == "Grid"
    assert by_name["UMG Grid Span"]["flow_slot"]["ColumnSpan"] == 2
    assert by_name["UMG Scroll Frame"]["scroll_overflow"] == "Both"
    assert by_name["UMG Scroll Fixed"]["scroll_position"] == "Fixed"


def test_multi_artboard_umg_session_reuses_one_document_resolution(
    monkeypatch,
) -> None:
    import app.painter_ui_umg_adapter as umg_adapter
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_object,
        create_ui_document,
    )

    document = create_ui_document(320, 180, name="First")
    first_artboard_id = document["active_artboard_id"]
    document, _first = add_ui_object(
        document,
        artboard_id=first_artboard_id,
        kind="text",
        name="First label",
    )
    document, second_artboard = add_ui_artboard(
        document,
        name="Second",
        width=640,
        height=360,
    )
    document, _second = add_ui_object(
        document,
        artboard_id=second_artboard["id"],
        kind="button",
        name="Second button",
    )
    expected = {
        artboard_id: umg_adapter.preflight_painter_umg(
            document,
            artboard_id=artboard_id,
        )
        for artboard_id in (first_artboard_id, second_artboard["id"])
    }

    prepare_calls = 0
    original_prepare = umg_adapter._prepare_painter_umg_conversion

    def counted_prepare(value):
        nonlocal prepare_calls
        prepare_calls += 1
        return original_prepare(value)

    monkeypatch.setattr(
        umg_adapter,
        "_prepare_painter_umg_conversion",
        counted_prepare,
    )
    session = umg_adapter.PainterUMGConversionSession(document)
    actual = {
        artboard_id: session.preflight(artboard_id=artboard_id)
        for artboard_id in session.artboard_ids
    }

    assert prepare_calls == 1
    assert actual == expected


def test_transformed_figma_auto_layout_is_an_explicit_umg_blocker() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document = create_ui_document(640, 360, name="Affine recovery")
    document, row = add_ui_object(
        document,
        kind="frame",
        name="Transformed Figma stack",
        width=320,
        height=180,
        content={
            "figma_auto_layout_recovery": {
                "status": "snapshot_absolute_geometry",
                "reason": "transformed_auto_layout_requires_affine_layout",
                "relative_transform": [[0.707, 0.707], [-0.707, 0.707]],
            }
        },
    )

    preflight = preflight_painter_umg(document)
    blocker = next(
        item for item in preflight["blockers"] if item["object_id"] == row["id"]
    )

    assert blocker["reasons"] == [
        "figma_transformed_auto_layout_requires_affine_layout"
    ]
    assert preflight["counts"]["Blocked"] == 1


def test_blocked_figma_affine_descendant_is_an_explicit_umg_blocker() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document = create_ui_document(640, 360, name="Affine blocker")
    document, row = add_ui_object(
        document,
        kind="path",
        name="Sheared child",
        content={
            "figma_affine_snapshot_geometry": {
                "status": "blocked_non_orthogonal_affine",
                "reason": (
                    "figma_affine_snapshot_requires_shear_or_reflection_support"
                ),
                "effective_linear_transform": [[1.0, 0.5], [0.0, 1.0]],
            }
        },
    )

    preflight = preflight_painter_umg(document)
    blocker = next(
        item for item in preflight["blockers"] if item["object_id"] == row["id"]
    )

    assert (
        "figma_affine_snapshot_requires_shear_or_reflection_support"
        in blocker["reasons"]
    )
