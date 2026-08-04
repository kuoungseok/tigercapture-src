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
    assert manifest["Version"] == 11
    assert manifest["VersionName"] == "1.0.0"
    assert source_manifest["Version"] == 11
    assert source_manifest["VersionName"] == "1.0.0"
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
    generation = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "Private"
        / "TigerStudioUMGGeneration.cpp"
    ).read_text(encoding="utf-8")
    import_header = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "Public"
        / "TigerStudioUMGImportSubsystem.h"
    ).read_text(encoding="utf-8")
    editor_build = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "TigerStudioUMGEditor.Build.cs"
    ).read_text(encoding="utf-8")
    assert "int32 SchemaVersion = 11;" in types
    assert "FTigerStudioUMGCanvasSlotRecord" in types
    assert "FVector2D AnchorMinimum = FVector2D::ZeroVector;" in types
    assert "FVector2D AnchorMaximum = FVector2D::ZeroVector;" in types
    assert "FMargin Offsets = FMargin(0.0, 0.0, 100.0, 100.0);" in types
    assert "FVector2D Alignment = FVector2D(0.5, 0.5);" in types
    assert "FTigerStudioUMGCanvasSlotRecord CanvasSlot;" in types
    assert "FTigerStudioUMGFlowSlotRecord" in types
    assert "FString PanelKind = TEXT(\"None\");" in types
    assert "FTigerStudioUMGFlowSlotRecord FlowSlot;" in types
    assert 'FString ScrollOverflow = TEXT("None");' in types
    assert 'FString ScrollPosition = TEXT("Scroll");' in types
    assert "FVector2D RenderTransformPivot = FVector2D(0.5, 0.5);" in types
    assert "FVector2D Anchor = FVector2D(0.5, 0.5);" in types
    assert "TArray<FString> BlockReasons;" in types
    assert "FTigerStudioUMGGradientStopRecord" in types
    assert "FTigerStudioUMGMaterialRecord" in types
    assert "FString Generator;" in types
    assert "TArray<FTigerStudioUMGGradientStopRecord> Stops;" in types
    assert "double Opacity = 1.0;" in types
    assert "FTigerStudioUMGStrokeRecord" in types
    assert "FTigerStudioUMGShadowRecord" in types
    assert "FVector2D Size = FVector2D(100.0, 100.0);" in types
    assert 'FString FillKind = TEXT("Solid");' in types
    assert 'FString FillColor = TEXT("#FFFFFFFF");' in types
    assert "FVector4 CornerRadii" in types
    assert "double CornerSmoothing = 0.0;" in types
    assert "FTigerStudioUMGStrokeRecord Stroke;" in types
    assert "FTigerStudioUMGShadowRecord DropShadow;" in types
    assert "FTigerStudioUMGShadowRecord InnerShadow;" in types
    assert "FMargin VisualPadding = FMargin(0.0);" in types
    assert "FTigerStudioUMGMaterialRecord Material;" in types
    assert "FTigerStudioUMGImageFillRecord" in types
    assert "FTigerStudioUMGImageCropRecord" in types
    assert "FTigerStudioUMGImageAdjustmentsRecord" in types
    assert "FTigerStudioUMGImageNineSliceRecord" in types
    assert "FTigerStudioUMGImageFillRecord ImageFill;" in types
    assert 'FString Mode = TEXT("Stretch");' in types
    assert "FVector2D SourceSize = FVector2D::ZeroVector;" in types
    assert "FVector2D FocalPoint = FVector2D(0.5, 0.5);" in types
    assert "FTigerStudioUMGImageCropRecord Crop;" in types
    assert "FTigerStudioUMGImageNineSliceRecord NineSlice;" in types
    assert "FVector4 CornerRadii" in types
    assert "Result.Document.SchemaVersion < 4" in preflight
    assert "Result.Document.SchemaVersion > 11" in preflight
    assert "SerializedSchemaVersion == 4" in preflight
    assert "AddV5DefaultsToV4Layers(DocumentObject);" in preflight
    assert "AddLegacyLayerDefaults(DocumentObject, SerializedSchemaVersion);" in preflight
    assert "AddV2DefaultsToLegacyMaterials(DocumentObject);" in preflight
    assert "MaterialSchema != TEXT(\"tigerstudio.umg.ui_material.v1\")" in preflight
    assert "ValidateRawV2MaterialLayers" in preflight
    assert "HasRawStroke" in preflight
    assert "HasRawShadow" in preflight
    assert "HasRawVisualPadding" in preflight
    assert "RawV2BlockReasons" in preflight
    assert "ValidateRawImageFillLayers" in preflight
    assert "RawImageFillBlockReasons" in preflight
    assert "image_fill_asset_id_missing" in preflight
    assert "image_fill_crop_record_invalid" in preflight
    assert "image_fill_adjustments_record_invalid" in preflight
    assert "image_fill_nine_slice_record_invalid" in preflight
    assert preflight.index(
        "const TArray<FString> RawV2BlockReasons"
    ) < preflight.index("FJsonObjectConverter::JsonObjectToUStruct")
    assert "ValidateMaterialLayer" in preflight
    assert "ui_material_generator_unsupported" in preflight
    assert "ui_material_gradient_stop_limit_exceeded" in preflight
    assert 'TEXT("tigerstudio.umg.ui_material.v2")' in preflight
    assert 'TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1")' in preflight
    assert 'TEXT("RoundedCard")' in preflight
    assert "ui_material_requires_schema_8" in preflight
    assert "ui_material_rounded_card_radii_invalid" in preflight
    assert "ui_material_rounded_card_stroke_invalid" in preflight
    assert "ui_material_rounded_card_drop_shadow_invalid" in preflight
    assert "ui_material_rounded_card_inner_shadow_invalid" in preflight
    assert "ui_material_visual_padding_invalid" in preflight
    assert "ExpectedVisualPadding" in preflight
    assert "RoundedCardRequiresDynamicSizeBinding" in preflight
    assert "Layer.CanvasSlot.AnchorMinimum.Equals(" in preflight
    assert 'ParentPanelKind == TEXT("Horizontal")' in preflight
    assert 'ParentPanelKind == TEXT("Vertical")' in preflight
    assert 'ParentPanelKind == TEXT("Grid")' in preflight
    assert (
        "rounded_card_runtime_resize_requires_dynamic_size_binding"
        in preflight
    )
    assert "baked_generation_unavailable" in preflight
    assert "umg_scroll_requires_schema_10" in preflight
    assert "umg_fixed_requires_scroll_parent" in preflight
    assert "umg_sticky_runtime_binding_unavailable" in preflight
    assert "ValidateImageFillLayer" in preflight
    assert "image_fill_requires_schema_11" in preflight
    assert "image_fill_resource_missing" in preflight
    assert "image_fill_adjustments_require_ui_material_or_bake" in preflight
    assert "image_fill_crop_rect_out_of_bounds" in preflight
    assert "image_fill_nine_slice_requires_stretch" in preflight
    assert (
        "image_fill_nine_slice_rounded_corners_require_ui_material_or_bake"
        in preflight
    )
    assert (
        "image_fill_tile_rounded_corners_require_ui_material_or_bake"
        in preflight
    )
    assert (
        "image_fill_runtime_resize_requires_dynamic_uv_binding"
        in preflight
    )
    assert "SchemaVersion >= 5" in generation
    assert "Layer.RenderTransformPivot" in generation
    assert "Slot->SetAnchors(FAnchors(" in generation
    assert "Slot->SetOffsets(Layer.CanvasSlot.Offsets);" in generation
    assert "Slot->SetAlignment(Layer.CanvasSlot.Alignment);" in generation
    assert "Slot->SetAlignment(Layer.Anchor);" in generation
    assert "Slot->SetAutoSize(false);" in generation
    assert '"Components/HorizontalBox.h"' in generation
    assert '"Components/VerticalBox.h"' in generation
    assert '"Components/GridPanel.h"' in generation
    assert '"Components/ScrollBox.h"' in generation
    assert '"Components/Overlay.h"' in generation
    assert '"Components/SizeBox.h"' in generation
    assert "WidgetTree->ConstructWidget<UHorizontalBox>" in generation
    assert "WidgetTree->ConstructWidget<UVerticalBox>" in generation
    assert "WidgetTree->ConstructWidget<UGridPanel>" in generation
    assert "WidgetTree->ConstructWidget<UScrollBox>" in generation
    assert "WidgetTree->ConstructWidget<UOverlay>" in generation
    assert "FixedParentPanels" in generation
    assert "Grid->AddChildToGrid" in generation
    assert "Slot->SetRowSpan" in generation
    assert "Slot->SetColumnSpan" in generation
    assert "Slot->SetPadding(Layer.FlowSlot.Padding);" in generation
    assert "Slot->SetSize(SlotSize);" in generation
    assert '"Components/ScaleBox.h"' in generation
    assert "MakeImageFillBrush" in generation
    assert "CreateImageFillWidget" in generation
    assert "Brush.SetResourceObject(Texture);" in generation
    assert "Brush.SetUVRegion(FBox2f(" in generation
    assert "ResolveImageFillSourceRegion" in generation
    assert "SourceRegion.PixelSize" in generation
    assert "Brush.Tiling = ESlateBrushTileType::Both;" in generation
    assert "Brush.DrawAs = ESlateBrushDrawType::Box;" in generation
    assert "Brush.DrawAs = ESlateBrushDrawType::RoundedBox;" in generation
    assert "FSlateBrushOutlineSettings(EffectiveRadii)" in generation
    assert "ScaleBox->SetStretch(EStretch::ScaleToFit);" in generation
    assert "ImageFillResourceIds" in generation
    assert "Image Fill resource did not import as UTexture2D" in generation
    assert 'Layer.Id + TEXT("#background")' in generation
    assert ".SetNormal(BackgroundBrush)" in generation
    assert "Button->AddChild(Label);" in generation
    assert "UUIMaterialFactoryNew" in generation
    assert "UMaterialExpressionCustom" in generation
    assert "GetMaterialExpressions(Material)" in generation
    assert "DeleteMaterialExpression(" in generation
    assert "Material->MaterialDomain = EMaterialDomain::MD_UI;" in generation
    assert "Material->BlendMode = EBlendMode::BLEND_Translucent;" in generation
    assert "Custom->Code = GradientCustomHlsl(Layer.Material);" in generation
    assert "GenerateRoundedCardMaterial" in generation
    assert "RoundedCardCustomHlsl" in generation
    assert "AppendRoundedDistanceHlsl" in generation
    assert 'TEXT("Tiger Rounded Card SDF / validated Custom HLSL")' in generation
    assert 'TEXT("CornerRadii")' in generation
    assert 'TEXT("GradientWidth")' in generation
    assert "Record.Width.X" in generation
    assert "float2 GradientBasisX = GradientEnd.xy - GradientStart.xy;" in generation
    assert "float2 GradientBasisY = GradientWidth.xy - GradientStart.xy;" in generation
    assert "float GradientDeterminant =" in generation
    assert "float2 GradientLocal =" in generation
    assert 'TEXT("StrokeAlignment")' in generation
    assert 'TEXT("DropShadowEnabled")' in generation
    assert 'TEXT("InnerShadowEnabled")' in generation
    assert "float StrokeMask =" in generation
    assert "float DropMask =" in generation
    assert "float InnerMask =" in generation
    assert (
        "float2 PixelPosition = UV * SurfaceSize - VisualPadding.xy;"
        in generation
    )
    assert 'TEXT("CardPoint - DropShadowOffset.xy")' in generation
    assert 'TEXT("CardPoint - InnerShadowOffset.xy")' in generation
    assert "AddCustomInput(Custom, TEXT(\"FillOpacity\"), FillOpacity);" in generation
    assert "Color,\n            5);" in generation
    assert "EMaterialProperty::MP_EmissiveColor" in generation
    assert "EMaterialProperty::MP_Opacity" in generation
    assert "Image->SetBrushFromMaterial(Material);" in generation
    assert 'FName(*(Layer.Id + TEXT("_Visual")))' in generation
    assert "Layer.Material.VisualPadding" in generation
    assert "Image->SetDesiredSizeOverride(SurfaceSize);" in generation
    assert "VisualSlot->SetPosition(FVector2D(" in generation
    assert "Widget = MaterialHost;" in generation
    assert "Result.GeneratedMaterialPaths.AddUnique(ObjectPath);" in generation
    assert "TArray<FString> GeneratedMaterialPaths;" in import_header
    assert "TMap<FString, FString> GeneratedWidgetClasses;" in import_header
    assert '"MaterialEditor"' in editor_build
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
