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


def _plugin_import_subsystem_source() -> str:
    source_root = Path(__file__).resolve().parents[1] / PLUGIN_SOURCE_RELATIVE_ROOT
    return (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "Private"
        / "TigerStudioUMGImportSubsystem.cpp"
    ).read_text(encoding="utf-8")


def test_component_instance_button_placement_skips_leaf_style_validation() -> None:
    preflight = _plugin_import_subsystem_source()

    assert preflight.count("if (HasValidComponentInstancePayload(Layer))") == 2
    assert 'InstanceId != LayerId' in preflight
    assert 'TEXT("component_id")' in preflight
    assert 'TEXT("property_values")' in preflight
    assert 'TEXT("resolved_overrides")' in preflight
    assert 'TEXT("slot_contents")' in preflight
    assert preflight.index(
        "if (HasValidComponentInstancePayload(Layer))"
    ) < preflight.index('const bool bButtonLayer = LayerKind == TEXT("Button");')
    typed_validator = preflight.index(
        "TArray<FString> ValidateButtonStyleLayer("
    )
    typed_exemption = preflight.index(
        "if (HasValidComponentInstancePayload(Layer))",
        typed_validator,
    )
    typed_missing_check = preflight.index(
        "Reasons.Add(TEXT(\"button_style_missing\"));",
        typed_validator,
    )
    assert typed_exemption < typed_missing_check


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
    assert manifest["Version"] == 21
    assert manifest["VersionName"] == "1.8.2"
    assert source_manifest["Version"] == 21
    assert source_manifest["VersionName"] == "1.8.2"
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
    render_cpp = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "Private"
        / "TigerStudioUMGRender.cpp"
    ).read_text(encoding="utf-8")
    editor_build = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "TigerStudioUMGEditor.Build.cs"
    ).read_text(encoding="utf-8")
    rounded_card_host_header = (
        source_root
        / "Source"
        / "TigerStudioUMG"
        / "Public"
        / "TigerStudioRoundedCardHost.h"
    ).read_text(encoding="utf-8")
    rounded_card_host_cpp = (
        source_root
        / "Source"
        / "TigerStudioUMG"
        / "Private"
        / "TigerStudioRoundedCardHost.cpp"
    ).read_text(encoding="utf-8")
    assert "int32 SchemaVersion = 19;" in types
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
    assert 'FString Visibility = TEXT("Visible");' in types
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
    assert 'FString SizeBinding = TEXT("FixedSize");' in types
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
    assert "FTigerStudioUMGFlipbookRecord" in types
    assert "FTigerStudioUMGFlipbookRecord Flipbook;" in types
    assert "int32 Columns = 1;" in types
    assert "int32 Rows = 1;" in types
    assert "int32 FrameCount = 1;" in types
    assert "double FramesPerSecond = 12.0;" in types
    assert "int32 StaticFrameOverride = -1;" in types
    assert "FTigerStudioUMGButtonStateRecord" in types
    assert "FTigerStudioUMGButtonStyleRecord" in types
    assert "FTigerStudioUMGButtonStyleRecord ButtonStyle;" in types
    assert 'FString Fill = TEXT("#4A4A4AFF");' in types
    assert 'FString Stroke = TEXT("#777777FF");' in types
    assert "double StrokeWidth = 1.0;" in types
    assert 'FString TextColor = TEXT("#FFFFFFFF");' in types
    assert "double FontSize = 24.0;" in types
    assert "int32 FontWeight = 700;" in types
    assert "FTigerStudioUMGButtonStateRecord Normal;" in types
    assert "FTigerStudioUMGButtonStateRecord Hovered;" in types
    assert "FTigerStudioUMGButtonStateRecord Pressed;" in types
    assert "FTigerStudioUMGButtonStateRecord Disabled;" in types
    assert "FTigerStudioUMGRenderResult" in import_header
    assert "RenderWidgetBlueprintToPng" in import_header
    assert "TMap<FString, FString> WidgetTextAudit;" in import_header
    assert "TMap<FString, FString> WidgetVisibilityAudit;" in import_header
    assert "TMap<FString, FString> ComponentInstanceAudit;" in import_header
    assert "CollectWidgetRuntimeAudit" in render_cpp
    assert "CollectComponentInstanceAudit" in render_cpp
    assert 'TEXT("before")' in render_cpp
    assert 'TEXT("after")' in render_cpp
    assert 'TEXT("/child_instance_property_values_json")' in render_cpp
    assert 'TEXT("/child_property_count")' in render_cpp
    assert 'TEXT("/target_found")' in render_cpp
    assert 'TEXT("/current_text")' in render_cpp
    assert 'TEXT("/current_visibility")' in render_cpp
    assert "Text->GetText().ToString()" in render_cpp
    assert "VisibilityAuditName(Child->GetVisibility())" in render_cpp
    assert "FWidgetRenderer" in render_cpp
    assert "FWidgetRenderer Renderer(false, true);" in render_cpp
    assert "FWidgetRenderer::CreateTargetFor(" in render_cpp
    assert "TF_Bilinear," in render_cpp
    assert "Renderer.DrawWidget(RenderTarget, SlateWidget" in render_cpp
    assert render_cpp.count(
        "Renderer.DrawWidget(RenderTarget, SlateWidget"
    ) == 1
    assert "intentionally a single-pass proof" in render_cpp
    assert "CollectRoundedCardRuntimeAudit(" in render_cpp
    assert "Result.RoundedCardSizeAudit" in render_cpp
    assert "Result.RoundedCardVisualSlotAudit" in render_cpp
    assert "ReadFlags.SetLinearToGamma(false);" in render_cpp
    assert "PNGCompressImageArray" in render_cpp
    assert "FinishAllCompilation" in render_cpp
    assert "Material->EnsureIsComplete();" in render_cpp
    assert "CollectWidgetBrushResources(" in render_cpp
    assert "VisitedOwners.Contains(Widget)" in render_cpp
    assert "Material->GetUsedTextures(UsedTextures);" in render_cpp
    assert "WaitForStreaming" in render_cpp
    assert "StreamAllResources" in render_cpp
    assert "if (bTypedImageFill && ButtonTexture)" in generation
    assert "CreateImageFillWidget" in generation
    assert 'FString Mode = TEXT("Stretch");' in types
    assert "FVector2D SourceSize = FVector2D::ZeroVector;" in types
    assert "FVector2D FocalPoint = FVector2D(0.5, 0.5);" in types
    assert "FTigerStudioUMGImageCropRecord Crop;" in types
    assert "FTigerStudioUMGImageNineSliceRecord NineSlice;" in types
    assert "FVector4 CornerRadii" in types
    assert "Result.Document.SchemaVersion < 4" in preflight
    assert "Result.Document.SchemaVersion > 19" in preflight
    assert "ValidateRawPanelRecords" in preflight
    assert preflight.index("bool TryGetFiniteNumber(") < preflight.index(
        "TArray<FString> ValidateRawPanelRecords("
    )
    assert "umg_overlay_panel_requires_schema_17" in preflight
    assert "umg_spacer_strategy_requires_linear_panel" in preflight
    assert "SerializedSchemaVersion == 4" in preflight
    assert "AddV5DefaultsToV4Layers(DocumentObject);" in preflight
    assert "AddLegacyLayerDefaults(DocumentObject, SerializedSchemaVersion);" in preflight
    assert "AddV2DefaultsToLegacyMaterials(DocumentObject);" in preflight
    assert "AddV2DefaultsToLegacyComponentMaterials(DocumentObject);" in preflight
    assert "AddMaterialSizeBindingDefaults(" in preflight
    assert "DynamicRoundedCardSizeSchemaVersion = 19" in preflight
    assert "ui_material_dynamic_size_binding_requires_schema_19" in preflight
    assert 'Layer.Material.SizeBinding != TEXT("WidgetGeometry")' in preflight
    assert "UTigerStudioRoundedCardHost" in generation
    assert "Layer.Material.SizeBinding" in generation
    assert "STigerStudioRoundedCardCanvas" in rounded_card_host_cpp
    assert "AllottedGeometry.GetLocalSize()" in rounded_card_host_cpp
    assert "SConstraintCanvas::OnPaint(" in rounded_card_host_cpp
    assert rounded_card_host_cpp.index(
        "Host->UpdateTigerMaterialSizeForGeometry("
    ) < rounded_card_host_cpp.index("return SConstraintCanvas::OnPaint(")
    assert "ComputeDesiredSize(float LayoutScaleMultiplier)" in rounded_card_host_cpp
    assert "return Host->TigerFixedCardSize;" in rounded_card_host_cpp
    assert "VisualSlot->SetSize(FVector2D::ZeroVector);" in rounded_card_host_cpp
    assert "TigerLastAppliedCardSize" in rounded_card_host_header
    assert "SetVectorParameterValue(" in rounded_card_host_cpp
    assert "ValidateRawDocumentRecords" in preflight
    assert "RawDocumentRecordBlockReasons" in preflight
    assert "ValidateRawButtonStyleLayers" in preflight
    assert "RawButtonStyleBlockReasons" in preflight
    assert "ValidateButtonStyleLayer" in preflight
    assert "button_style_missing" in preflight
    assert "button_style_requires_schema_16" in preflight
    assert "button_style_schema_unsupported" in preflight
    assert "button_style_state_font_metrics_require_runtime_binding" in preflight
    assert "ValidateRawLayerVisibility" in preflight
    assert "RawVisibilityBlockReasons" in preflight
    assert "const bool bVisibilityRequired" in preflight
    assert "SchemaVersion >= LayerVisibilitySchemaVersion" in preflight
    assert 'if (!Layer->HasField(TEXT("Visibility")))' in preflight
    assert "umg_visibility_requires_schema_16" in preflight
    assert "umg_visibility_record_invalid" in preflight
    assert "umg_visibility_unsupported" in preflight
    assert "umg_layers_record_invalid" in preflight
    assert "umg_layer_record_invalid" in preflight
    assert "umg_layer_disposition_invalid" in preflight
    assert "umg_resources_record_invalid" in preflight
    assert "umg_resource_record_invalid" in preflight
    assert 'Disposition == TEXT("Native")' in preflight
    assert 'Disposition == TEXT("Material")' in preflight
    assert 'Disposition == TEXT("Baked")' in preflight
    assert 'Disposition == TEXT("Blocked")' in preflight
    assert "MaterialSchema != TEXT(\"tigerstudio.umg.ui_material.v1\")" in preflight
    assert "ValidateRawV2MaterialLayers" in preflight
    assert "HasRawStroke" in preflight
    assert "HasRawShadow" in preflight
    assert "HasRawVisualPadding" in preflight
    assert "RawV2BlockReasons" in preflight
    assert "ValidateRawImageFillLayers" in preflight
    assert "RawImageFillBlockReasons" in preflight
    assert "ValidateRawFlipbookLayers" in preflight
    assert "RawFlipbookBlockReasons" in preflight
    assert "ValidateRawMaterializedBakedLayers" in preflight
    assert "RawBakedBlockReasons" in preflight
    assert "ValidateFlipbookLayer" in preflight
    assert "flipbook_requires_schema_12" in preflight
    assert "flipbook_generator_unsupported" in preflight
    assert "flipbook_atlas_resource_missing" in preflight
    assert "flipbook_atlas_capacity_exceeded" in preflight
    assert "flipbook_static_frame_override_out_of_range" in preflight
    assert "image_fill_asset_id_missing" in preflight
    assert "image_fill_crop_record_invalid" in preflight
    assert "image_fill_adjustments_record_invalid" in preflight
    assert "image_fill_nine_slice_record_invalid" in preflight
    assert preflight.index(
        "const TArray<FString> RawDocumentRecordBlockReasons"
    ) < preflight.index("AddLegacyLayerDefaults(DocumentObject, SerializedSchemaVersion);")
    assert preflight.index(
        "const TArray<FString> RawDocumentRecordBlockReasons"
    ) < preflight.index("FJsonObjectConverter::JsonObjectToUStruct")
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
    assert "CollectTypedComponentSlotRootIds" in preflight
    assert "SyntheticOverlayRootIds.Contains(Layer.Id)" in preflight
    assert "bMainAxisFill && bHorizontalFill" in preflight
    assert "bMainAxisFill && bVerticalFill" in preflight
    assert "SyntheticOverlayRootIds))" in preflight
    assert "Layer.CanvasSlot.AnchorMinimum.Equals(" in preflight
    assert 'ParentPanelKind == TEXT("Horizontal")' in preflight
    assert 'ParentPanelKind == TEXT("Vertical")' in preflight
    assert 'ParentPanelKind == TEXT("Grid")' in preflight
    assert (
        "rounded_card_runtime_resize_requires_dynamic_size_binding"
        in preflight
    )
    assert "image_fill_runtime_resize_requires_dynamic_uv_binding" in preflight
    assert "geometry=%.3fx%.3f" in render_cpp
    assert "baked_generation_unavailable" in preflight
    assert "ValidateMaterializedBakedLayer" in preflight
    assert "baked_static_vector_layer_kind_unsupported" in preflight
    assert "baked_image_fill_contract_invalid" in preflight
    assert "baked_satisfied_gate_invalid" in preflight
    assert "StaticAppearanceBakeSchemaVersion = 14" in preflight
    assert "StaticTextureBakeSchemaVersion = 15" in preflight
    assert 'TEXT("tigerstudio.umg.static_appearance_bake.v1")' in preflight
    assert 'TEXT("static_figma_appearance_png")' in preflight
    assert 'TEXT("tigerstudio.umg.static_texture_bake.v1")' in preflight
    assert 'TEXT("static_figma_texture_png")' in preflight
    assert (
        'TEXT("figma_texture_effect_requires_ui_material_or_deterministic_bake")'
        in preflight
    )
    assert (
        'TEXT("static_appearance_bake_requires_schema_14")' in preflight
    )
    assert 'TEXT("static_texture_bake_requires_schema_15")' in preflight
    assert 'TEXT("baked_static_texture_requires_schema_15")' in preflight
    assert 'TEXT("baked_plan_kind_conflict")' in preflight
    assert "ValidateMaterializedStaticAppearanceBake" in preflight
    assert "ValidateStaticAppearancePng" in preflight
    assert "ValidateStaticTextureEffect" in preflight
    assert 'TEXT("clip_to_shape")' in preflight
    assert 'TEXT("noise_size_vector")' in preflight
    assert 'TEXT("baked_static_appearance_contract_mismatch")' in preflight
    assert 'TEXT("baked_static_appearance_intended_gate_invalid")' in preflight
    assert 'TEXT("tigerstudio_umg_schema15_materialized")' in preflight
    assert "source_canonical_json" in preflight
    assert "effect_canonical_json" in preflight
    assert "FJsonValue::CompareEqual" in preflight
    assert "FCrc::MemCrc32" in preflight
    assert "ERGBFormat::RGBA" in preflight
    assert "StaticAppearanceBakeMaxMetadataBytes" in preflight
    assert "baked_static_appearance_layout_preservation_invalid" in preflight
    assert "baked_static_appearance_provenance_invalid" in preflight
    assert (
        "texture2d_image_fill_from_static_appearance_bake"
        in preflight
    )
    assert 'TEXT("static_appearance_png_bake")' in preflight
    assert "texture2d_image_fill_from_static_texture_bake" in preflight
    assert 'TEXT("static_texture_png_bake")' in preflight
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
    assert 'Payload->TryGetBoolField(TEXT("auto_wrap"), bAutoWrap);' in generation
    assert 'Payload->TryGetNumberField(TEXT("font_weight"), FontWeight);' in generation
    assert 'Payload->TryGetStringField(TEXT("font_size_unit"), Unit);' in generation
    assert 'TEXT("css_px_96dpi")' in generation
    assert "AuthoredSize * TigerPointsPerInch / TigerCssPixelsPerInch" in generation
    assert 'TEXT("legacy_slate_points")' in generation
    assert "Font.Size = PayloadFontSizeInSlatePoints(Payload, FontSize);" in generation
    assert "PayloadFontSizeInSlatePoints(" in generation
    assert "ApplyTypedButtonLabelStyle(" in generation
    assert "label_font" in generation
    assert "authored_size" in generation
    assert "applied_slate_points" in generation
    assert "display_css_px_96dpi" in generation
    assert "Font.TypefaceFontName = ButtonTypefaceForWeight(" in generation
    assert "Text->SetAutoWrapText(bAutoWrap);" in generation
    assert "Text->SetClipping(EWidgetClipping::ClipToBounds);" in generation
    assert "Defaults->DesignTimeSize = FVector2D(" in generation
    assert "FMath::Max(1, Document.Width)" in generation
    assert "FMath::Max(1, Document.Height)" in generation
    assert "Defaults->DesignSizeMode = EDesignPreviewSizeMode::Custom;" in generation
    assert '"Components/HorizontalBox.h"' in generation
    assert '"Components/VerticalBox.h"' in generation
    assert '"Components/GridPanel.h"' in generation
    assert '"Components/ScrollBox.h"' in generation
    assert '"Components/Overlay.h"' in generation
    assert '"Components/OverlaySlot.h"' in generation
    assert '"Components/Spacer.h"' in generation
    assert '"Components/SizeBox.h"' in generation
    assert "WidgetTree->ConstructWidget<UHorizontalBox>" in generation
    assert "WidgetTree->ConstructWidget<UVerticalBox>" in generation
    assert "WidgetTree->ConstructWidget<UGridPanel>" in generation
    assert "WidgetTree->ConstructWidget<UScrollBox>" in generation
    assert "WidgetTree->ConstructWidget<UOverlay>" in generation
    assert 'Layer.PanelKind == TEXT("Overlay")' in generation
    assert "Overlay->AddChildToOverlay(HostWidget)" in generation
    assert "ConstructWidget<USpacer>" in generation
    assert "SpacerSlot->SetSize(SpacerSlotSize);" in generation
    assert "FixedParentPanels" in generation
    assert "Grid->AddChildToGrid" in generation
    assert "Slot->SetRowSpan" in generation
    assert "Slot->SetColumnSpan" in generation
    assert "Slot->SetPadding(Layer.FlowSlot.Padding);" in generation
    assert "Slot->SetSize(SlotSize);" in generation
    assert '"Components/ScaleBox.h"' in generation
    assert "MakeImageFillBrush" in generation
    assert "CreateImageFillWidget" in generation
    assert "const bool bBaked = Document.SchemaVersion >= 13" in generation
    assert "else if (bBaked)" in generation
    assert "Materialized Baked texture could not be loaded" in generation
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
    assert '"Brushes/SlateRoundedBoxBrush.h"' in generation
    assert "MakeTypedButtonStyle" in generation
    assert "FSlateRoundedBoxBrush(" in generation
    assert ".SetNormalForeground(" in generation
    assert ".SetHoveredForeground(" in generation
    assert ".SetPressedForeground(" in generation
    assert ".SetDisabledForeground(" in generation
    assert "Font.TypefaceFontName = ButtonTypefaceForWeight(" in generation
    assert "Label->SetColorAndOpacity(FSlateColor::UseForeground());" in generation
    assert "Button->SetIsEnabled(Layer.ButtonStyle.Enabled);" in generation
    assert "Result.GeneratedButtonStyleAudit.Add(" in generation
    assert "ApplyTypedLayerVisibility" in generation
    assert "ESlateVisibility::HitTestInvisible" in generation
    assert "Result.GeneratedWidgetVisibilityAudit.Add(" in generation
    assert "UUIMaterialFactoryNew" in generation
    assert "UMaterialExpressionCustom" in generation
    assert "UMaterialExpressionTextureSampleParameter2D" in generation
    assert "UMaterialExpressionTime" in generation
    assert "GetMaterialExpressions(Material)" in generation
    assert "DeleteMaterialExpression(" in generation
    assert "Material->MaterialDomain = EMaterialDomain::MD_UI;" in generation
    assert "Material->BlendMode = EBlendMode::BLEND_Translucent;" in generation
    assert "Custom->Code = GradientCustomHlsl(Layer.Material);" in generation
    assert "GenerateFlipbookMaterial" in generation
    assert "FlipbookCustomHlsl" in generation
    assert 'TEXT("Tiger Flipbook Atlas / validated fixed Custom HLSL")' in generation
    assert 'TEXT("AtlasTexture")' in generation
    assert 'TEXT("StaticFrameOverride")' in generation
    assert "TextureSample->Coordinates.Connect(0, Custom);" in generation
    assert "TextureSample->Texture = AtlasTexture;" in generation
    assert 'TEXT("RGB"),' in generation
    assert 'TEXT("A"),' in generation
    assert "bTextureRgbToEmissive" in generation
    assert "bTextureAlphaToOpacity" in generation
    assert "LoadFlipbookTexture(Layer, ResourcePaths)" in generation
    assert "FlipbookResourceIds" in generation
    assert "GenerateRoundedCardMaterial" in generation
    assert "RoundedCardCustomHlsl" in generation
    assert "AppendRoundedDistanceHlsl" in generation
    assert 'TEXT("Tiger Rounded Card SDF / validated Custom HLSL")' in generation
    assert 'TEXT("CornerRadii")' in generation
    assert "float4 EffectiveCornerRadii = CornerRadii *" in generation
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
    assert "TMap<FString, FString> GeneratedButtonStyleAudit;" in import_header
    assert "TMap<FString, FString> GeneratedWidgetVisibilityAudit;" in import_header
    assert '"MaterialEditor"' in editor_build
    assert '"ImageWrapper"' in editor_build
    assert "FString::Join(Result.BlockReasons" in preflight
    if "bundled" in root.parts:
        assert not (root / "Source").exists()
        assert not (root / "Intermediate").exists()


def test_source_schema15_texture_bake_contract_is_strict_and_distinct() -> None:
    source_root = Path(__file__).resolve().parents[1] / PLUGIN_SOURCE_RELATIVE_ROOT
    preflight = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "Private"
        / "TigerStudioUMGImportSubsystem.cpp"
    ).read_text(encoding="utf-8")

    texture_effect = preflight.split(
        "bool ValidateStaticTextureEffect",
        1,
    )[1].split(
        "TArray<FString> ValidateMaterializedStaticAppearanceBake",
        1,
    )[0]
    for field in (
        "type",
        "radius",
        "noise_size",
        "clip_to_shape",
        "noise_size_vector",
    ):
        assert f'TEXT("{field}")' in texture_effect
    for forbidden in (
        "color",
        "blend_mode",
        "noise_type",
        "density",
        "secondary_color",
        "opacity",
        "visible",
    ):
        assert f'TEXT("{forbidden}")' not in texture_effect
    assert 'Type != TEXT("texture")' in texture_effect
    assert 'TEXT("clip_to_shape"),\n            EJson::Boolean' in texture_effect
    assert 'HasExactFields(Vector, {TEXT("x"), TEXT("y")})' in texture_effect
    assert "Radius < 0.0" in texture_effect
    assert "NoiseSize < 0.0" in texture_effect
    assert "X < 0.0" in texture_effect
    assert "Y < 0.0" in texture_effect

    appearance = preflight.split(
        "TArray<FString> ValidateMaterializedStaticAppearanceBake",
        1,
    )[1].split(
        "TArray<FString> ValidateMaterializedBakedLayer",
        1,
    )[0]
    assert "bStaticTextureBake" in appearance
    assert "StaticTextureBakeSchema" in appearance
    assert "StaticAppearanceBakeSchema" in appearance
    assert 'TEXT("tigerstudio_umg_schema15_materialized")' in appearance
    assert 'TEXT("tigerstudio_umg_schema14_materialized")' in appearance
    assert '!bStaticTextureBake && Bake->HasField(TEXT("intended_gate"))' in appearance
    assert '!bStaticTextureBake && Source->HasField(TEXT("intended_gate"))' in appearance


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


def test_schema18_reusable_component_generation_contract_is_explicit() -> None:
    source_root = (
        Path(__file__).resolve().parents[1] / PLUGIN_SOURCE_RELATIVE_ROOT
    )
    runtime_public = source_root / "Source" / "TigerStudioUMG" / "Public"
    runtime_private = source_root / "Source" / "TigerStudioUMG" / "Private"
    editor_private = (
        source_root / "Source" / "TigerStudioUMGEditor" / "Private"
    )
    editor_public = (
        source_root / "Source" / "TigerStudioUMGEditor" / "Public"
    )
    types = (runtime_public / "TigerStudioUMGTypes.h").read_text(
        encoding="utf-8"
    )
    component_header = (
        runtime_public / "TigerStudioComponentWidget.h"
    ).read_text(encoding="utf-8")
    component_runtime = (
        runtime_private / "TigerStudioComponentWidget.cpp"
    ).read_text(encoding="utf-8")
    generated_header = (
        runtime_public / "TigerStudioGeneratedWidget.h"
    ).read_text(encoding="utf-8")
    generated_runtime = (
        runtime_private / "TigerStudioGeneratedWidget.cpp"
    ).read_text(encoding="utf-8")
    generation = (editor_private / "TigerStudioUMGGeneration.cpp").read_text(
        encoding="utf-8"
    )
    render_cpp = (editor_private / "TigerStudioUMGRender.cpp").read_text(
        encoding="utf-8"
    )
    preflight = (
        editor_private / "TigerStudioUMGImportSubsystem.cpp"
    ).read_text(encoding="utf-8")
    import_header = (
        editor_public / "TigerStudioUMGImportSubsystem.h"
    ).read_text(encoding="utf-8")

    for record in (
        "FTigerStudioUMGComponentPropertyBindingRecord",
        "FTigerStudioUMGComponentPropertyRecord",
        "FTigerStudioUMGComponentSlotRecord",
        "FTigerStudioUMGComponentRecord",
        "FTigerStudioUMGComponentSlotContentRecord",
        "FTigerStudioUMGComponentInstanceRecord",
    ):
        assert record in types
    assert "TArray<FTigerStudioUMGComponentRecord> Components;" in types
    assert (
        "TArray<FTigerStudioUMGComponentInstanceRecord> ComponentInstances;"
        in types
    )
    assert "class TIGERSTUDIOUMG_API UTigerStudioComponentWidget" in (
        component_header
    )
    assert "TigerResolvedOverridesJson" in component_header
    assert "TigerInstancePropertyValuesJson" in component_header
    assert "TigerInstancePropertyValuesJson" in component_runtime
    assert "InstancePropertyValues->TryGetField(PropertyRecord.Name)" in (
        component_runtime
    )
    assert 'TEXT("content.text")' in component_runtime
    assert 'TEXT("visible")' in component_runtime
    assert (
        "TArray<FTigerStudioUMGComponentInstanceRecord> "
        "TigerComponentInstances;"
        in generated_header
    )
    assert "for (const FTigerStudioUMGComponentInstanceRecord& Instance" in (
        generated_runtime
    )
    assert "void ApplyTigerComponentInstances();" in generated_header
    assert "virtual void NativePreConstruct() override;" in generated_header
    assert "void UTigerStudioGeneratedWidget::NativePreConstruct()" in (
        generated_runtime
    )
    assert generated_runtime.count("ApplyTigerComponentInstances();") >= 3
    assert "WidgetTree->FindWidget(FName(*Instance.LayerId))" in (
        generated_runtime
    )
    assert (
        "GetDefaultObject<UTigerStudioComponentWidget>()"
        in generated_runtime
    )
    assert (
        "Component->TigerComponentProperties =\n"
        "                Defaults->TigerComponentProperties;"
        in generated_runtime
    )
    assert (
        "Component->TigerComponentInstances =\n"
        "                Defaults->TigerComponentInstances;"
        in generated_runtime
    )
    assert "if (Component->TigerComponentId.IsEmpty())" in generated_runtime
    assert "if (Component->TigerSourceProvider.IsEmpty())" in generated_runtime
    assert "Component->TigerInstancePropertyValuesJson" in generated_runtime
    assert "Component->TigerResolvedOverridesJson" in generated_runtime
    assert "Component->ApplyTigerComponentInstances();" in generated_runtime
    assert "Component->ApplyTigerComponentProperties();" in generated_runtime
    assert "GeneratedWidget->ApplyTigerComponentInstances();" in render_cpp
    assert "GenerateComponentBlueprint" in generation
    assert "SortComponentDefinitions" in generation
    assert 'TEXT("WBP_TS_C_")' in generation
    assert "GeneratedComponentClasses" in generation
    assert "ComponentInstancesByLayer" in generation
    assert "SetContentForSlot" in generation
    # UMG Designer creates child UserWidgets as uninitialized UWidget
    # templates. Using ConstructWidget<UUserWidget> would eagerly clone the
    # foreign tree and lose instance-only NamedSlot template bindings.
    assert generation.count("ConstructWidget<UWidget>(") == 2
    assert "ConstructWidget<UUserWidget>(" not in generation
    assert generation.count("TigerInstancePropertyValuesJson") == 2
    assert "MakeComponentInstanceRecord" in generation
    assert (
        "Defaults->TigerComponentInstances = NestedComponentInstances;"
        in generation
    )
    assert (
        "Defaults->TigerComponentInstances = Document.ComponentInstances;"
        in generation
    )
    assert "ComponentWidgetClasses.Add(" in generation
    assert 'Layer.Id + TEXT("#named_slot")' in generation
    assert "component_dependency_cycle" in generation
    assert "ValidateRawComponentRecords" in preflight
    assert "RawLayerValidationDocument" in preflight
    assert "ValidateTypedComponentContract" in preflight
    assert "ValidateComponentPropertyValues" in preflight
    assert "ValidateResolvedComponentOverrides" in preflight
    assert "umg_component_property_runtime_unsupported" in preflight
    assert "RawImplicitDefinitionPlacementIds" in preflight
    assert "ImplicitDefinitionPlacementIds" in preflight
    assert "RawDefinitionOwnerByLayer" in preflight
    assert "DefinitionOwnerByLayer" in preflight
    assert "Id == LayerId" in preflight
    assert "Instance.Id == Instance.LayerId" in preflight
    assert "*ComponentRoot == LayerId" in preflight
    assert "Instance.LayerId == (*Component)->RootLayerId" in preflight
    assert "JsonObjectsEqualExact" in preflight
    assert "RawImplicitComponentDefaults" in preflight
    assert "TypedImplicitComponentDefaults" in preflight
    assert preflight.count(
        "umg_implicit_component_property_values_not_default"
    ) == 2
    assert preflight.count(
        "umg_component_definition_layer_leaked_to_screen"
    ) == 2
    assert "GeneratedComponentAssetPaths" in import_header
    assert "GeneratedComponentClassPaths" in import_header
    assert "int32 GeneratedComponentCount = 0;" in import_header


def test_legacy_documents_receive_empty_component_defaults_before_strict_read() -> None:
    source_root = (
        Path(__file__).resolve().parents[1] / PLUGIN_SOURCE_RELATIVE_ROOT
    )
    preflight = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "Private"
        / "TigerStudioUMGImportSubsystem.cpp"
    ).read_text(encoding="utf-8")
    defaults = preflight.split(
        "void AddLegacyComponentDocumentDefaults(",
        1,
    )[1].split("TSharedPtr<FJsonObject> DefaultStrokeJson()", 1)[0]

    assert "SchemaVersion >= ComponentSchemaVersion" in defaults
    assert 'DocumentObject->HasField(TEXT("Components"))' in defaults
    assert 'DocumentObject->HasField(TEXT("ComponentInstances"))' in defaults
    assert 'TEXT("Components"),' in defaults
    assert 'TEXT("ComponentInstances"),' in defaults
    call = (
        "AddLegacyComponentDocumentDefaults(\n"
        "        DocumentObject,\n"
        "        SerializedSchemaVersion);"
    )
    assert call in preflight
    assert preflight.index("RawComponentBlockReasons") < preflight.index(call)
    assert preflight.index(call) < preflight.index(
        "FJsonObjectConverter::JsonObjectToUStruct"
    )


def test_schema17_spacing_outer_fields_are_strict_for_every_layer() -> None:
    source_root = (
        Path(__file__).resolve().parents[1] / PLUGIN_SOURCE_RELATIVE_ROOT
    )
    preflight = (
        source_root
        / "Source"
        / "TigerStudioUMGEditor"
        / "Private"
        / "TigerStudioUMGImportSubsystem.cpp"
    ).read_text(encoding="utf-8")
    raw = preflight.split(
        "TArray<FString> ValidateRawPanelRecords(",
        1,
    )[1].split(
        "TArray<FString> ValidateRawV2MaterialLayers(",
        1,
    )[0]
    typed = preflight.split(
        "const bool bIsGroup =\n"
        "            Layer.Kind == ETigerStudioUMGLayerKind::Group;",
        1,
    )[1].split("switch (Layer.Disposition)", 1)[0]

    assert (
        "const bool bSpacingRequired =\n"
        "            SchemaVersion >= SpacingStrategySchemaVersion;"
        in raw
    )
    assert "&& bIsGroup" not in raw.split(
        "const bool bSpacingRequired =", 1
    )[1].split(";", 1)[0]
    for field in (
        "SpacingStrategy",
        "SpacerSizeRule",
        "SpacerFillCoefficient",
    ):
        assert f'Layer->HasField(TEXT("{field}"))' in raw
    for reason in (
        "umg_non_group_spacing_strategy_must_be_padding",
        "umg_non_group_spacer_size_rule_must_be_auto",
        "umg_non_group_spacer_fill_coefficient_must_be_one",
    ):
        assert reason in raw
        assert reason in typed
    assert 'if (!bIsGroup)' in raw
    assert 'if (!bIsGroup)' in typed
    assert (
        'else if (SpacingStrategy == TEXT("Spacer")' in raw
    )
    assert (
        'if (SpacingStrategy == TEXT("Spacer")' in typed
    )
    assert preflight.index("RawPanelBlockReasons") < preflight.index(
        "FJsonObjectConverter::JsonObjectToUStruct"
    )


def test_generation_preserves_canvas_paint_order_and_audits_spacers() -> None:
    source_root = (
        Path(__file__).resolve().parents[1] / PLUGIN_SOURCE_RELATIVE_ROOT
    )
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
    configure = generation.split("void ConfigureWidget(", 1)[1].split(
        "FTigerStudioUMGGenerationResult\n"
        "UTigerStudioUMGImportSubsystem::GenerateDocumentFile(",
        1,
    )[0]
    canvas_branch = configure.split(
        "if (UCanvasPanel* Canvas = Cast<UCanvasPanel>(Parent))",
        1,
    )[1].split("UWidget* HostWidget = Widget;", 1)[0]
    overlay_branch = configure.split(
        "else if (UOverlay* Overlay = Cast<UOverlay>(Parent))",
        1,
    )[1]

    # Generation is intentionally two-pass (groups, then leaves), so every
    # root and nested CanvasPanel slot must paint by stable document order.
    assert "TMap<FString, int32> LayerPaintOrders;" in generation
    assert "LayerIndex < Document.Layers.Num();" in generation
    assert (
        "LayerPaintOrders.Add(Document.Layers[LayerIndex].Id, LayerIndex);"
        in generation
    )
    # Four legacy screen construction branches plus the schema-18 component
    # instance branch all preserve the same authored Canvas paint order.
    assert generation.count("LayerPaintOrders.FindRef(Layer.Id),") == 5
    assert "Slot->SetZOrder(CanvasZOrder);" in canvas_branch
    assert generation.count("Slot->SetZOrder(CanvasZOrder);") == 1

    # Overlay has insertion-order paint semantics; Canvas ZOrder must not leak
    # into that branch.
    assert "Overlay->AddChildToOverlay(HostWidget)" in overlay_branch
    assert "SetZOrder" not in overlay_branch

    # Synthetic native spacers are auditable without changing the authored
    # layer count reported by GeneratedWidgetCount.
    assert "TMap<FString, FString>& GeneratedWidgetClasses" in configure
    assert generation.count('TEXT("#spacer_before")') == 2
    assert generation.count('TEXT("#spacer_after")') == 2
    assert generation.count("Layer.Id + AuditSuffix") == 2
    assert generation.count("Spacer->GetClass()->GetName()") == 2
    assert "GeneratedWidgetCount" not in configure
    assert "Synthetic\n     * entries are audit evidence" in import_header
