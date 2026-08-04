#include "TigerStudioUMGImportSubsystem.h"

#include "Dom/JsonObject.h"
#include "JsonObjectConverter.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
TSharedPtr<FJsonObject> Vector2DJson(const double X, const double Y)
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("X"), X);
    Result->SetNumberField(TEXT("Y"), Y);
    return Result;
}

TSharedPtr<FJsonObject> Vector4Json(
    const double X,
    const double Y,
    const double Z,
    const double W)
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("X"), X);
    Result->SetNumberField(TEXT("Y"), Y);
    Result->SetNumberField(TEXT("Z"), Z);
    Result->SetNumberField(TEXT("W"), W);
    return Result;
}

TSharedPtr<FJsonObject> MarginJson(
    const double Left,
    const double Top,
    const double Right,
    const double Bottom)
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("Left"), Left);
    Result->SetNumberField(TEXT("Top"), Top);
    Result->SetNumberField(TEXT("Right"), Right);
    Result->SetNumberField(TEXT("Bottom"), Bottom);
    return Result;
}

void AddV5DefaultsToV4Layers(const TSharedPtr<FJsonObject>& DocumentObject)
{
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        if (!Layer)
        {
            continue;
        }

        if (!Layer->HasField(TEXT("CanvasSlot")))
        {
            TSharedPtr<FJsonObject> CanvasSlot = MakeShared<FJsonObject>();
            CanvasSlot->SetObjectField(
                TEXT("AnchorMinimum"),
                Vector2DJson(0.0, 0.0));
            CanvasSlot->SetObjectField(
                TEXT("AnchorMaximum"),
                Vector2DJson(0.0, 0.0));
            TSharedPtr<FJsonObject> Offsets = MakeShared<FJsonObject>();
            Offsets->SetNumberField(TEXT("Left"), 0.0);
            Offsets->SetNumberField(TEXT("Top"), 0.0);
            Offsets->SetNumberField(TEXT("Right"), 100.0);
            Offsets->SetNumberField(TEXT("Bottom"), 100.0);
            CanvasSlot->SetObjectField(TEXT("Offsets"), Offsets);
            CanvasSlot->SetObjectField(
                TEXT("Alignment"),
                Vector2DJson(0.5, 0.5));
            Layer->SetObjectField(TEXT("CanvasSlot"), CanvasSlot);
        }

        if (!Layer->HasField(TEXT("RenderTransformPivot")))
        {
            double PivotX = 0.5;
            double PivotY = 0.5;
            const TSharedPtr<FJsonObject>* LegacyAnchor = nullptr;
            if (Layer->TryGetObjectField(TEXT("Anchor"), LegacyAnchor)
                && LegacyAnchor
                && LegacyAnchor->IsValid())
            {
                (*LegacyAnchor)->TryGetNumberField(TEXT("X"), PivotX);
                (*LegacyAnchor)->TryGetNumberField(TEXT("Y"), PivotY);
            }
            Layer->SetObjectField(
                TEXT("RenderTransformPivot"),
                Vector2DJson(PivotX, PivotY));
        }
    }
}

void AddLegacyLayerDefaults(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer = LayerValue
            ? LayerValue->AsObject()
            : nullptr;
        if (!Layer)
        {
            continue;
        }
        if (SchemaVersion < 6 && !Layer->HasField(TEXT("Material")))
        {
            Layer->SetObjectField(
                TEXT("Material"),
                MakeShared<FJsonObject>());
        }
        if (SchemaVersion < 7)
        {
            if (!Layer->HasField(TEXT("PanelKind")))
            {
                Layer->SetStringField(TEXT("PanelKind"), TEXT("None"));
            }
            if (!Layer->HasField(TEXT("FlowSlot")))
            {
                TSharedPtr<FJsonObject> FlowSlot = MakeShared<FJsonObject>();
                FlowSlot->SetObjectField(
                    TEXT("Padding"),
                    MarginJson(0.0, 0.0, 0.0, 0.0));
                FlowSlot->SetStringField(
                    TEXT("HorizontalAlignment"),
                    TEXT("Fill"));
                FlowSlot->SetStringField(
                    TEXT("VerticalAlignment"),
                    TEXT("Fill"));
                FlowSlot->SetStringField(TEXT("SizeRule"), TEXT("Auto"));
                FlowSlot->SetNumberField(TEXT("FillCoefficient"), 1.0);
                Layer->SetObjectField(TEXT("FlowSlot"), FlowSlot);
            }
        }
        if (SchemaVersion < 10)
        {
            if (!Layer->HasField(TEXT("ScrollOverflow")))
            {
                Layer->SetStringField(TEXT("ScrollOverflow"), TEXT("None"));
            }
            if (!Layer->HasField(TEXT("ScrollPosition")))
            {
                Layer->SetStringField(TEXT("ScrollPosition"), TEXT("Scroll"));
            }
        }
        if (SchemaVersion < 11 && !Layer->HasField(TEXT("ImageFill")))
        {
            Layer->SetObjectField(
                TEXT("ImageFill"),
                MakeShared<FJsonObject>());
        }
    }
}

TSharedPtr<FJsonObject> DefaultStrokeJson()
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("Width"), 0.0);
    Result->SetStringField(TEXT("Alignment"), TEXT("Inside"));
    Result->SetStringField(TEXT("Color"), TEXT("#00000000"));
    return Result;
}

TSharedPtr<FJsonObject> DefaultShadowJson()
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetBoolField(TEXT("Enabled"), false);
    Result->SetStringField(TEXT("Color"), TEXT("#00000000"));
    Result->SetObjectField(TEXT("Offset"), Vector2DJson(0.0, 0.0));
    Result->SetNumberField(TEXT("Blur"), 0.0);
    Result->SetNumberField(TEXT("Spread"), 0.0);
    return Result;
}

void AddV2DefaultsToLegacyMaterials(
    const TSharedPtr<FJsonObject>& DocumentObject)
{
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer = LayerValue
            ? LayerValue->AsObject()
            : nullptr;
        const TSharedPtr<FJsonObject>* MaterialField = nullptr;
        if (!Layer
            || !Layer->TryGetObjectField(TEXT("Material"), MaterialField)
            || !MaterialField
            || !MaterialField->IsValid())
        {
            continue;
        }
        const TSharedPtr<FJsonObject> Material = *MaterialField;
        FString MaterialSchema;
        if (!Material->TryGetStringField(TEXT("Schema"), MaterialSchema)
            || MaterialSchema != TEXT("tigerstudio.umg.ui_material.v1"))
        {
            continue;
        }

        if (!Material->HasField(TEXT("Size")))
        {
            Material->SetObjectField(TEXT("Size"), Vector2DJson(100.0, 100.0));
        }
        if (!Material->HasField(TEXT("FillKind")))
        {
            Material->SetStringField(TEXT("FillKind"), TEXT("Solid"));
        }
        if (!Material->HasField(TEXT("FillColor")))
        {
            Material->SetStringField(TEXT("FillColor"), TEXT("#FFFFFFFF"));
        }
        if (!Material->HasField(TEXT("CornerRadii")))
        {
            Material->SetObjectField(
                TEXT("CornerRadii"),
                Vector4Json(0.0, 0.0, 0.0, 0.0));
        }
        if (!Material->HasField(TEXT("CornerSmoothing")))
        {
            Material->SetNumberField(TEXT("CornerSmoothing"), 0.0);
        }
        if (!Material->HasField(TEXT("Stroke")))
        {
            Material->SetObjectField(TEXT("Stroke"), DefaultStrokeJson());
        }
        if (!Material->HasField(TEXT("DropShadow")))
        {
            Material->SetObjectField(
                TEXT("DropShadow"),
                DefaultShadowJson());
        }
        if (!Material->HasField(TEXT("InnerShadow")))
        {
            Material->SetObjectField(
                TEXT("InnerShadow"),
                DefaultShadowJson());
        }
        if (!Material->HasField(TEXT("VisualPadding")))
        {
            Material->SetObjectField(
                TEXT("VisualPadding"),
                MarginJson(0.0, 0.0, 0.0, 0.0));
        }
    }
}

bool HasRawFieldType(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field,
    const EJson Type)
{
    if (!Object)
    {
        return false;
    }
    const TSharedPtr<FJsonValue>* Value = Object->Values.Find(Field);
    return Value
        && Value->IsValid()
        && !(*Value)->IsNull()
        && (*Value)->Type == Type;
}

TSharedPtr<FJsonObject> RawObjectField(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    const TSharedPtr<FJsonObject>* Value = nullptr;
    if (!Object
        || !Object->TryGetObjectField(Field, Value)
        || !Value
        || !Value->IsValid())
    {
        return nullptr;
    }
    return *Value;
}

bool HasRawVector2(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    const TSharedPtr<FJsonObject> Value = RawObjectField(Object, Field);
    return HasRawFieldType(Value, TEXT("X"), EJson::Number)
        && HasRawFieldType(Value, TEXT("Y"), EJson::Number);
}

bool HasRawVector4(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    const TSharedPtr<FJsonObject> Value = RawObjectField(Object, Field);
    return HasRawFieldType(Value, TEXT("X"), EJson::Number)
        && HasRawFieldType(Value, TEXT("Y"), EJson::Number)
        && HasRawFieldType(Value, TEXT("Z"), EJson::Number)
        && HasRawFieldType(Value, TEXT("W"), EJson::Number);
}

bool HasRawStroke(const TSharedPtr<FJsonObject>& Material)
{
    const TSharedPtr<FJsonObject> Stroke = RawObjectField(
        Material,
        TEXT("Stroke"));
    return HasRawFieldType(Stroke, TEXT("Width"), EJson::Number)
        && HasRawFieldType(Stroke, TEXT("Alignment"), EJson::String)
        && HasRawFieldType(Stroke, TEXT("Color"), EJson::String);
}

bool HasRawShadow(
    const TSharedPtr<FJsonObject>& Material,
    const TCHAR* Field)
{
    const TSharedPtr<FJsonObject> Shadow = RawObjectField(Material, Field);
    return HasRawFieldType(Shadow, TEXT("Enabled"), EJson::Boolean)
        && HasRawFieldType(Shadow, TEXT("Color"), EJson::String)
        && HasRawVector2(Shadow, TEXT("Offset"))
        && HasRawFieldType(Shadow, TEXT("Blur"), EJson::Number)
        && HasRawFieldType(Shadow, TEXT("Spread"), EJson::Number);
}

bool HasRawVisualPadding(const TSharedPtr<FJsonObject>& Material)
{
    const TSharedPtr<FJsonObject> Padding = RawObjectField(
        Material,
        TEXT("VisualPadding"));
    return HasRawFieldType(Padding, TEXT("Left"), EJson::Number)
        && HasRawFieldType(Padding, TEXT("Top"), EJson::Number)
        && HasRawFieldType(Padding, TEXT("Right"), EJson::Number)
        && HasRawFieldType(Padding, TEXT("Bottom"), EJson::Number);
}

void AddRawMaterialReason(
    TArray<FString>& Reasons,
    const FString& LayerId,
    const TCHAR* Reason)
{
    Reasons.AddUnique(LayerId + TEXT(":") + Reason);
}

TArray<FString> ValidateRawV2MaterialLayers(
    const TSharedPtr<FJsonObject>& DocumentObject)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        const TSharedPtr<FJsonObject> Material = RawObjectField(
            Layer,
            TEXT("Material"));
        if (!Layer || !Material)
        {
            continue;
        }

        FString Schema;
        FString Generator;
        FString Kind;
        Material->TryGetStringField(TEXT("Schema"), Schema);
        Material->TryGetStringField(TEXT("Generator"), Generator);
        Material->TryGetStringField(TEXT("Kind"), Kind);
        const bool bRoundedCard =
            Schema == TEXT("tigerstudio.umg.ui_material.v2")
            || Generator
                == TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1")
            || Kind == TEXT("RoundedCard")
            || Material->HasField(TEXT("CornerRadii"))
            || Material->HasField(TEXT("CornerSmoothing"))
            || Material->HasField(TEXT("Stroke"))
            || Material->HasField(TEXT("DropShadow"))
            || Material->HasField(TEXT("InnerShadow"))
            || Material->HasField(TEXT("VisualPadding"));
        if (!bRoundedCard)
        {
            continue;
        }

        FString LayerId = TEXT("<unknown>");
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        FString CoordinateSpace;
        Material->TryGetStringField(
            TEXT("CoordinateSpace"),
            CoordinateSpace);
        if (Schema != TEXT("tigerstudio.umg.ui_material.v2"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_schema_unsupported"));
        }
        if (Generator
            != TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_generator_unsupported"));
        }
        if (Kind != TEXT("RoundedCard"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_kind_unsupported"));
        }
        if (CoordinateSpace != TEXT("LocalUV"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_coordinate_space_unsupported"));
        }
        if (!HasRawVector2(Material, TEXT("Size")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_size_invalid"));
        }
        if (!HasRawFieldType(Material, TEXT("FillKind"), EJson::String))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_fill_kind_unsupported"));
        }
        if (!HasRawFieldType(Material, TEXT("FillColor"), EJson::String))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_fill_color_invalid"));
        }
        if (!HasRawFieldType(Material, TEXT("Opacity"), EJson::Number))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_opacity_invalid"));
        }
        if (!HasRawVector2(Material, TEXT("Start"))
            || !HasRawVector2(Material, TEXT("End"))
            || !HasRawVector2(Material, TEXT("Width")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_gradient_geometry_invalid"));
        }

        const TArray<TSharedPtr<FJsonValue>>* Stops = nullptr;
        if (!Material->TryGetArrayField(TEXT("Stops"), Stops)
            || !Stops
            || Stops->Num() < 2)
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_gradient_requires_two_stops"));
        }
        else if (Stops->Num() > 16)
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_gradient_stop_limit_exceeded"));
        }
        else
        {
            for (const TSharedPtr<FJsonValue>& StopValue : *Stops)
            {
                const TSharedPtr<FJsonObject> Stop =
                    StopValue && StopValue->Type == EJson::Object
                    ? StopValue->AsObject()
                    : nullptr;
                if (!HasRawFieldType(
                        Stop,
                        TEXT("Position"),
                        EJson::Number)
                    || !HasRawFieldType(
                        Stop,
                        TEXT("Color"),
                        EJson::String))
                {
                    AddRawMaterialReason(
                        Reasons,
                        LayerId,
                        TEXT("ui_material_gradient_stop_invalid"));
                    break;
                }
            }
        }
        if (!HasRawVector4(Material, TEXT("CornerRadii")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_radii_invalid"));
        }
        if (!HasRawFieldType(
                Material,
                TEXT("CornerSmoothing"),
                EJson::Number))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_smoothing_invalid"));
        }
        if (!HasRawStroke(Material))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_stroke_invalid"));
        }
        if (!HasRawShadow(Material, TEXT("DropShadow")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_drop_shadow_invalid"));
        }
        if (!HasRawShadow(Material, TEXT("InnerShadow")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_inner_shadow_invalid"));
        }
        if (!HasRawVisualPadding(Material))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_visual_padding_invalid"));
        }
    }
    return Reasons;
}

TArray<FString> ValidateRawImageFillLayers(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        const TSharedPtr<FJsonObject> ImageFill = RawObjectField(
            Layer,
            TEXT("ImageFill"));
        if (!Layer || !ImageFill || ImageFill->Values.IsEmpty())
        {
            continue;
        }

        FString LayerId = TEXT("<unknown>");
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        const auto AddReason = [&Reasons, &LayerId](const TCHAR* Reason)
        {
            Reasons.AddUnique(LayerId + TEXT(":") + Reason);
        };
        if (SchemaVersion < 11)
        {
            AddReason(TEXT("image_fill_requires_schema_11"));
        }

        FString AssetId;
        if (!ImageFill->TryGetStringField(TEXT("AssetId"), AssetId)
            || AssetId.IsEmpty())
        {
            AddReason(TEXT("image_fill_asset_id_missing"));
        }
        if (!HasRawFieldType(ImageFill, TEXT("Mode"), EJson::String))
        {
            AddReason(TEXT("image_fill_mode_unsupported"));
        }
        if (!HasRawVector2(ImageFill, TEXT("SourceSize")))
        {
            AddReason(TEXT("image_fill_source_size_invalid"));
        }
        if (!HasRawVector2(ImageFill, TEXT("FocalPoint")))
        {
            AddReason(TEXT("image_fill_focal_point_invalid"));
        }
        if (!HasRawFieldType(ImageFill, TEXT("TileScale"), EJson::Number))
        {
            AddReason(TEXT("image_fill_tile_scale_invalid"));
        }
        if (!HasRawFieldType(ImageFill, TEXT("Opacity"), EJson::Number))
        {
            AddReason(TEXT("image_fill_opacity_invalid"));
        }
        if (!HasRawFieldType(ImageFill, TEXT("Tint"), EJson::String))
        {
            AddReason(TEXT("image_fill_tint_invalid"));
        }
        if (!HasRawVector4(ImageFill, TEXT("CornerRadii")))
        {
            AddReason(TEXT("image_fill_corner_radii_invalid"));
        }

        const TSharedPtr<FJsonObject> Crop = RawObjectField(
            ImageFill,
            TEXT("Crop"));
        if (!HasRawFieldType(Crop, TEXT("Enabled"), EJson::Boolean)
            || !HasRawFieldType(Crop, TEXT("Units"), EJson::String)
            || !HasRawFieldType(Crop, TEXT("X"), EJson::Number)
            || !HasRawFieldType(Crop, TEXT("Y"), EJson::Number)
            || !HasRawFieldType(Crop, TEXT("Width"), EJson::Number)
            || !HasRawFieldType(Crop, TEXT("Height"), EJson::Number))
        {
            AddReason(TEXT("image_fill_crop_record_invalid"));
        }

        const TSharedPtr<FJsonObject> Adjustments = RawObjectField(
            ImageFill,
            TEXT("Adjustments"));
        if (!HasRawFieldType(
                Adjustments,
                TEXT("Exposure"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Contrast"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Saturation"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Temperature"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Tint"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Highlights"),
                EJson::Number))
        {
            AddReason(TEXT("image_fill_adjustments_record_invalid"));
        }

        const TSharedPtr<FJsonObject> NineSlice = RawObjectField(
            ImageFill,
            TEXT("NineSlice"));
        if (!HasRawFieldType(NineSlice, TEXT("Enabled"), EJson::Boolean)
            || !HasRawFieldType(NineSlice, TEXT("Units"), EJson::String)
            || !HasRawFieldType(NineSlice, TEXT("Left"), EJson::Number)
            || !HasRawFieldType(NineSlice, TEXT("Top"), EJson::Number)
            || !HasRawFieldType(NineSlice, TEXT("Right"), EJson::Number)
            || !HasRawFieldType(NineSlice, TEXT("Bottom"), EJson::Number))
        {
            AddReason(TEXT("image_fill_nine_slice_record_invalid"));
        }
    }
    return Reasons;
}

bool IsFiniteVector2D(const FVector2D& Value)
{
    return FMath::IsFinite(Value.X) && FMath::IsFinite(Value.Y);
}

bool IsValidMaterialColor(const FString& Value)
{
    if (Value.Len() != 9 || Value[0] != TEXT('#'))
    {
        return false;
    }
    for (int32 Index = 1; Index < Value.Len(); ++Index)
    {
        if (!FChar::IsHexDigit(Value[Index]))
        {
            return false;
        }
    }
    return true;
}

void ValidateGradientStops(
    const FTigerStudioUMGMaterialRecord& Material,
    TArray<FString>& Reasons)
{
    if (Material.Stops.Num() < 2)
    {
        Reasons.Add(TEXT("ui_material_gradient_requires_two_stops"));
        return;
    }
    if (Material.Stops.Num() > 16)
    {
        Reasons.Add(TEXT("ui_material_gradient_stop_limit_exceeded"));
        return;
    }

    double PreviousPosition = -1.0;
    for (const FTigerStudioUMGGradientStopRecord& Stop : Material.Stops)
    {
        if (!FMath::IsFinite(Stop.Position)
            || Stop.Position < 0.0
            || Stop.Position > 1.0
            || !IsValidMaterialColor(Stop.Color))
        {
            Reasons.Add(TEXT("ui_material_gradient_stop_invalid"));
            break;
        }
        if (Stop.Position < PreviousPosition)
        {
            Reasons.Add(TEXT("ui_material_gradient_stops_not_sorted"));
            break;
        }
        PreviousPosition = Stop.Position;
    }
}

bool IsValidShadow(
    const FTigerStudioUMGShadowRecord& Shadow)
{
    return IsValidMaterialColor(Shadow.Color)
        && IsFiniteVector2D(Shadow.Offset)
        && FMath::IsFinite(Shadow.Blur)
        && Shadow.Blur >= 0.0
        && FMath::IsFinite(Shadow.Spread);
}

FMargin ExpectedVisualPadding(
    const FTigerStudioUMGStrokeRecord& Stroke,
    const FTigerStudioUMGShadowRecord& DropShadow)
{
    const double OutsideStroke = Stroke.Alignment == TEXT("Outside")
        ? Stroke.Width
        : Stroke.Alignment == TEXT("Center") ? Stroke.Width * 0.5 : 0.0;
    double Extent = 0.0;
    double OffsetX = 0.0;
    double OffsetY = 0.0;
    if (DropShadow.Enabled)
    {
        Extent = FMath::Max(0.0, DropShadow.Blur + DropShadow.Spread);
        OffsetX = DropShadow.Offset.X;
        OffsetY = DropShadow.Offset.Y;
    }
    return FMargin(
        OutsideStroke + FMath::Max(0.0, Extent - OffsetX),
        OutsideStroke + FMath::Max(0.0, Extent - OffsetY),
        OutsideStroke + FMath::Max(0.0, Extent + OffsetX),
        OutsideStroke + FMath::Max(0.0, Extent + OffsetY));
}

bool RoundedCardRequiresDynamicSizeBinding(
    const FTigerStudioUMGLayerRecord& Layer,
    const TMap<FString, FString>& ParentPanelKinds)
{
    if (!Layer.CanvasSlot.AnchorMinimum.Equals(
            Layer.CanvasSlot.AnchorMaximum,
            0.000001))
    {
        return true;
    }
    const FString* ParentPanelKind = ParentPanelKinds.Find(Layer.ParentId);
    if (!ParentPanelKind)
    {
        return false;
    }
    return *ParentPanelKind == TEXT("Horizontal")
        || *ParentPanelKind == TEXT("Vertical")
        || *ParentPanelKind == TEXT("Grid");
}

bool HasImageFillCornerRadii(const FVector4& Radii)
{
    return Radii.X > 0.0001
        || Radii.Y > 0.0001
        || Radii.Z > 0.0001
        || Radii.W > 0.0001;
}

bool HasUnsupportedImageAdjustments(
    const FTigerStudioUMGImageAdjustmentsRecord& Adjustments)
{
    const double Values[] = {
        Adjustments.Exposure,
        Adjustments.Contrast,
        Adjustments.Saturation,
        Adjustments.Temperature,
        Adjustments.Tint,
        Adjustments.Highlights,
    };
    for (const double Value : Values)
    {
        if (!FMath::IsFinite(Value) || !FMath::IsNearlyZero(Value, 0.0001))
        {
            return true;
        }
    }
    return false;
}

TArray<FString> ValidateImageFillLayer(
    const FTigerStudioUMGLayerRecord& Layer,
    const int32 SchemaVersion,
    const TMap<FString, FString>& ResourceKinds,
    const TMap<FString, FString>& ParentPanelKinds)
{
    TArray<FString> Reasons;
    const FTigerStudioUMGImageFillRecord& ImageFill = Layer.ImageFill;
    if (ImageFill.AssetId.IsEmpty())
    {
        return Reasons;
    }

    if (SchemaVersion < 11)
    {
        Reasons.Add(TEXT("image_fill_requires_schema_11"));
    }
    if (Layer.Kind != ETigerStudioUMGLayerKind::Group
        && Layer.Kind != ETigerStudioUMGLayerKind::Shape
        && Layer.Kind != ETigerStudioUMGLayerKind::Image
        && Layer.Kind != ETigerStudioUMGLayerKind::Button)
    {
        Reasons.Add(TEXT("image_fill_layer_kind_unsupported"));
    }
    if (!Layer.AssetId.IsEmpty() && Layer.AssetId != ImageFill.AssetId)
    {
        Reasons.Add(TEXT("image_fill_asset_id_mismatch"));
    }
    const FString* ResourceKind = ResourceKinds.Find(ImageFill.AssetId);
    if (!ResourceKind)
    {
        Reasons.Add(TEXT("image_fill_resource_missing"));
    }
    else if (!ResourceKind->Equals(TEXT("texture"), ESearchCase::IgnoreCase)
        && !ResourceKind->Equals(TEXT("image"), ESearchCase::IgnoreCase))
    {
        Reasons.Add(TEXT("image_fill_resource_kind_unsupported"));
    }

    const bool bStretch = ImageFill.Mode == TEXT("Stretch");
    const bool bFit = ImageFill.Mode == TEXT("Fit");
    const bool bFill = ImageFill.Mode == TEXT("Fill");
    const bool bCrop = ImageFill.Mode == TEXT("Crop");
    const bool bTile = ImageFill.Mode == TEXT("Tile");
    if (!bStretch && !bFit && !bFill && !bCrop && !bTile)
    {
        Reasons.Add(
            TEXT("image_fill_mode_unsupported:")
            + (ImageFill.Mode.IsEmpty() ? TEXT("empty") : ImageFill.Mode));
    }

    if (!IsFiniteVector2D(ImageFill.SourceSize)
        || ImageFill.SourceSize.X < 0.0
        || ImageFill.SourceSize.Y < 0.0
        || ((ImageFill.SourceSize.X <= 0.0)
            != (ImageFill.SourceSize.Y <= 0.0)))
    {
        Reasons.Add(TEXT("image_fill_source_size_invalid"));
    }
    if (!IsFiniteVector2D(ImageFill.FocalPoint)
        || ImageFill.FocalPoint.X < 0.0
        || ImageFill.FocalPoint.X > 1.0
        || ImageFill.FocalPoint.Y < 0.0
        || ImageFill.FocalPoint.Y > 1.0)
    {
        Reasons.Add(TEXT("image_fill_focal_point_invalid"));
    }
    if (!FMath::IsFinite(ImageFill.TileScale)
        || ImageFill.TileScale <= 0.0)
    {
        Reasons.Add(TEXT("image_fill_tile_scale_invalid"));
    }
    if (!FMath::IsFinite(ImageFill.Opacity)
        || ImageFill.Opacity < 0.0
        || ImageFill.Opacity > 1.0)
    {
        Reasons.Add(TEXT("image_fill_opacity_invalid"));
    }
    if (!IsValidMaterialColor(ImageFill.Tint))
    {
        Reasons.Add(TEXT("image_fill_tint_invalid"));
    }
    if (HasUnsupportedImageAdjustments(ImageFill.Adjustments))
    {
        Reasons.Add(
            TEXT("image_fill_adjustments_require_ui_material_or_bake"));
    }

    const FTigerStudioUMGImageCropRecord& Crop = ImageFill.Crop;
    if (bCrop && !Crop.Enabled)
    {
        Reasons.Add(TEXT("image_fill_crop_rect_missing"));
    }
    if (Crop.Enabled)
    {
        const bool bNormalized = Crop.Units == TEXT("Normalized");
        const bool bPixels = Crop.Units == TEXT("Pixels");
        if (!bNormalized && !bPixels)
        {
            Reasons.Add(TEXT("image_fill_crop_units_invalid"));
        }
        const bool bFiniteRect = FMath::IsFinite(Crop.X)
            && FMath::IsFinite(Crop.Y)
            && FMath::IsFinite(Crop.Width)
            && FMath::IsFinite(Crop.Height);
        if (!bFiniteRect
            || Crop.X < 0.0
            || Crop.Y < 0.0
            || Crop.Width <= 0.0
            || Crop.Height <= 0.0)
        {
            Reasons.Add(TEXT("image_fill_crop_rect_invalid"));
        }
        else if ((bNormalized
                    && (Crop.X + Crop.Width > 1.000001
                        || Crop.Y + Crop.Height > 1.000001))
            || (bPixels
                && ImageFill.SourceSize.X > 0.0
                && ImageFill.SourceSize.Y > 0.0
                && (Crop.X + Crop.Width > ImageFill.SourceSize.X + 0.0001
                    || Crop.Y + Crop.Height
                        > ImageFill.SourceSize.Y + 0.0001)))
        {
            Reasons.Add(TEXT("image_fill_crop_rect_out_of_bounds"));
        }
    }

    const FVector4& Radii = ImageFill.CornerRadii;
    if (!FMath::IsFinite(Radii.X)
        || !FMath::IsFinite(Radii.Y)
        || !FMath::IsFinite(Radii.Z)
        || !FMath::IsFinite(Radii.W)
        || Radii.X < 0.0
        || Radii.Y < 0.0
        || Radii.Z < 0.0
        || Radii.W < 0.0
        || Layer.Size.X <= 0.0
        || Layer.Size.Y <= 0.0
        || Radii.X + Radii.Y > Layer.Size.X + 0.0001
        || Radii.W + Radii.Z > Layer.Size.X + 0.0001
        || Radii.X + Radii.W > Layer.Size.Y + 0.0001
        || Radii.Y + Radii.Z > Layer.Size.Y + 0.0001)
    {
        Reasons.Add(TEXT("image_fill_corner_radii_invalid"));
    }

    const FTigerStudioUMGImageNineSliceRecord& NineSlice =
        ImageFill.NineSlice;
    if (NineSlice.Enabled)
    {
        FVector2D NineSliceSourceSize = ImageFill.SourceSize;
        if (Crop.Enabled)
        {
            if (Crop.Units == TEXT("Pixels"))
            {
                NineSliceSourceSize = FVector2D(
                    Crop.Width,
                    Crop.Height);
            }
            else if (Crop.Units == TEXT("Normalized")
                && ImageFill.SourceSize.X > 0.0
                && ImageFill.SourceSize.Y > 0.0)
            {
                NineSliceSourceSize = FVector2D(
                    ImageFill.SourceSize.X * Crop.Width,
                    ImageFill.SourceSize.Y * Crop.Height);
            }
        }
        if (!bStretch)
        {
            Reasons.Add(TEXT("image_fill_nine_slice_requires_stretch"));
        }
        if (HasImageFillCornerRadii(Radii))
        {
            Reasons.Add(
                TEXT(
                    "image_fill_nine_slice_rounded_corners_require_ui_material_or_bake"));
        }
        const bool bPixels = NineSlice.Units == TEXT("Pixels");
        if (!bPixels)
        {
            Reasons.Add(TEXT("image_fill_nine_slice_units_invalid"));
        }
        const bool bFiniteMargins = FMath::IsFinite(NineSlice.Left)
            && FMath::IsFinite(NineSlice.Top)
            && FMath::IsFinite(NineSlice.Right)
            && FMath::IsFinite(NineSlice.Bottom);
        if (!bFiniteMargins
            || NineSlice.Left < 0.0
            || NineSlice.Top < 0.0
            || NineSlice.Right < 0.0
            || NineSlice.Bottom < 0.0)
        {
            Reasons.Add(TEXT("image_fill_nine_slice_margins_invalid"));
        }
        else if (bPixels
                && NineSliceSourceSize.X > 0.0
                && NineSliceSourceSize.Y > 0.0
                && (NineSlice.Left + NineSlice.Right
                        >= NineSliceSourceSize.X
                    || NineSlice.Top + NineSlice.Bottom
                        >= NineSliceSourceSize.Y))
        {
            Reasons.Add(TEXT("image_fill_nine_slice_margins_out_of_bounds"));
        }
    }
    if (bTile && HasImageFillCornerRadii(Radii))
    {
        Reasons.Add(
            TEXT("image_fill_tile_rounded_corners_require_ui_material_or_bake"));
    }
    if (bFill && RoundedCardRequiresDynamicSizeBinding(
            Layer,
            ParentPanelKinds))
    {
        Reasons.Add(
            TEXT("image_fill_runtime_resize_requires_dynamic_uv_binding"));
    }
    return Reasons;
}

TArray<FString> ValidateMaterialLayer(
    const FTigerStudioUMGLayerRecord& Layer,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const FTigerStudioUMGMaterialRecord& Material = Layer.Material;
    const bool bLegacyGradient =
        Material.Schema == TEXT("tigerstudio.umg.ui_material.v1");
    const bool bRoundedCard =
        Material.Schema == TEXT("tigerstudio.umg.ui_material.v2");
    if (!bLegacyGradient && !bRoundedCard)
    {
        Reasons.Add(TEXT("ui_material_schema_unsupported"));
        return Reasons;
    }

    if (Layer.Kind != ETigerStudioUMGLayerKind::Image
        && Layer.Kind != ETigerStudioUMGLayerKind::Shape)
    {
        Reasons.Add(TEXT("ui_material_layer_kind_unsupported"));
    }
    if (Material.CoordinateSpace != TEXT("LocalUV"))
    {
        Reasons.Add(TEXT("ui_material_coordinate_space_unsupported"));
    }

    if (bLegacyGradient)
    {
        if (Material.Generator != TEXT("tiger_ui_gradient_custom_hlsl_v1"))
        {
            Reasons.Add(TEXT("ui_material_generator_unsupported"));
        }
        if (Material.Kind != TEXT("LinearGradient")
            && Material.Kind != TEXT("RadialGradient"))
        {
            Reasons.Add(TEXT("ui_material_kind_unsupported"));
        }
        ValidateGradientStops(Material, Reasons);
        return Reasons;
    }

    if (SchemaVersion < 8)
    {
        Reasons.Add(TEXT("ui_material_requires_schema_8"));
    }
    if (Material.Generator
        != TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1"))
    {
        Reasons.Add(TEXT("ui_material_generator_unsupported"));
    }
    if (Material.Kind != TEXT("RoundedCard"))
    {
        Reasons.Add(TEXT("ui_material_kind_unsupported"));
    }
    const bool bValidSize = IsFiniteVector2D(Material.Size)
        && Material.Size.X > 0.0
        && Material.Size.Y > 0.0;
    if (!bValidSize)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_size_invalid"));
    }

    const bool bSolidFill = Material.FillKind == TEXT("Solid");
    const bool bLinearFill = Material.FillKind == TEXT("LinearGradient");
    const bool bRadialFill = Material.FillKind == TEXT("RadialGradient");
    if (!bSolidFill && !bLinearFill && !bRadialFill)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_fill_kind_unsupported"));
    }
    if (!IsValidMaterialColor(Material.FillColor))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_fill_color_invalid"));
    }
    if (!FMath::IsFinite(Material.Opacity)
        || Material.Opacity < 0.0
        || Material.Opacity > 1.0)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_opacity_invalid"));
    }
    if (!IsFiniteVector2D(Material.Start)
        || !IsFiniteVector2D(Material.End)
        || !IsFiniteVector2D(Material.Width))
    {
        Reasons.Add(TEXT("ui_material_gradient_geometry_invalid"));
    }
    ValidateGradientStops(Material, Reasons);

    const FVector4& Radii = Material.CornerRadii;
    if (!FMath::IsFinite(Radii.X)
        || !FMath::IsFinite(Radii.Y)
        || !FMath::IsFinite(Radii.Z)
        || !FMath::IsFinite(Radii.W)
        || Radii.X < 0.0
        || Radii.Y < 0.0
        || Radii.Z < 0.0
        || Radii.W < 0.0)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_radii_invalid"));
    }
    else if (bValidSize
        && (Radii.X + Radii.Y > Material.Size.X + 0.000001
        || Radii.W + Radii.Z > Material.Size.X + 0.000001
        || Radii.X + Radii.W > Material.Size.Y + 0.000001
        || Radii.Y + Radii.Z > Material.Size.Y + 0.000001))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_radii_exceed_size"));
    }
    if (!FMath::IsFinite(Material.CornerSmoothing)
        || Material.CornerSmoothing < 0.0
        || Material.CornerSmoothing > 1.0)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_smoothing_invalid"));
    }

    if (!FMath::IsFinite(Material.Stroke.Width)
        || Material.Stroke.Width < 0.0
        || (Material.Stroke.Alignment != TEXT("Inside")
            && Material.Stroke.Alignment != TEXT("Center")
            && Material.Stroke.Alignment != TEXT("Outside"))
        || !IsValidMaterialColor(Material.Stroke.Color))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_stroke_invalid"));
    }
    if (!IsValidShadow(Material.DropShadow))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_drop_shadow_invalid"));
    }
    if (!IsValidShadow(Material.InnerShadow))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_inner_shadow_invalid"));
    }

    const FMargin& Padding = Material.VisualPadding;
    if (!FMath::IsFinite(Padding.Left)
        || !FMath::IsFinite(Padding.Top)
        || !FMath::IsFinite(Padding.Right)
        || !FMath::IsFinite(Padding.Bottom)
        || Padding.Left < 0.0
        || Padding.Top < 0.0
        || Padding.Right < 0.0
        || Padding.Bottom < 0.0)
    {
        Reasons.Add(TEXT("ui_material_visual_padding_invalid"));
    }
    else
    {
        const FMargin Expected = ExpectedVisualPadding(
            Material.Stroke,
            Material.DropShadow);
        if (!FMath::IsNearlyEqual(Padding.Left, Expected.Left, 0.0001)
            || !FMath::IsNearlyEqual(Padding.Top, Expected.Top, 0.0001)
            || !FMath::IsNearlyEqual(Padding.Right, Expected.Right, 0.0001)
            || !FMath::IsNearlyEqual(Padding.Bottom, Expected.Bottom, 0.0001))
        {
            Reasons.Add(TEXT("ui_material_visual_padding_invalid"));
        }
    }
    return Reasons;
}
}

FTigerStudioUMGPreflightResult
UTigerStudioUMGImportSubsystem::PreflightDocumentFile(const FString& DocumentPath) const
{
    FTigerStudioUMGPreflightResult Result;
    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *DocumentPath))
    {
        Result.Message = FString::Printf(TEXT("Could not read Tiger UMG document: %s"), *DocumentPath);
        return Result;
    }

    TSharedPtr<FJsonObject> DocumentObject;
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, DocumentObject)
        || !DocumentObject)
    {
        Result.Message = TEXT("Could not parse Tiger UMG document JSON.");
        return Result;
    }

    int32 SerializedSchemaVersion = 0;
    DocumentObject->TryGetNumberField(
        TEXT("SchemaVersion"),
        SerializedSchemaVersion);
    if (SerializedSchemaVersion < 4 || SerializedSchemaVersion > 11)
    {
        Result.Message = FString::Printf(
            TEXT("Unsupported Tiger UMG schema version: %d"),
            SerializedSchemaVersion);
        return Result;
    }
    const TArray<FString> RawV2BlockReasons =
        ValidateRawV2MaterialLayers(DocumentObject);
    if (!RawV2BlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawV2BlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by unsupported generation layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TArray<FString> RawImageFillBlockReasons =
        ValidateRawImageFillLayers(
            DocumentObject,
            SerializedSchemaVersion);
    if (!RawImageFillBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawImageFillBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid Image Fill layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    if (SerializedSchemaVersion == 4)
    {
        AddV5DefaultsToV4Layers(DocumentObject);
    }
    AddLegacyLayerDefaults(DocumentObject, SerializedSchemaVersion);
    AddV2DefaultsToLegacyMaterials(DocumentObject);

    FText FailureReason;
    if (!FJsonObjectConverter::JsonObjectToUStruct(
            DocumentObject.ToSharedRef(),
            &Result.Document,
            0,
            0,
            true,
            &FailureReason))
    {
        Result.Message = FailureReason.ToString();
        return Result;
    }

    if (Result.Document.SchemaVersion < 4
        || Result.Document.SchemaVersion > 11)
    {
        Result.Message = FString::Printf(
            TEXT("Unsupported Tiger UMG schema version: %d"),
            Result.Document.SchemaVersion);
        return Result;
    }
    if (Result.Document.Provider.IsEmpty() || Result.Document.DocumentId.IsEmpty())
    {
        Result.Message = TEXT("Provider and DocumentId are required.");
        return Result;
    }
    if (Result.Document.Width <= 0 || Result.Document.Height <= 0)
    {
        Result.Message = TEXT("Document dimensions must be positive.");
        return Result;
    }

    Result.ResourceCount = Result.Document.Resources.Num();
    Result.InteractionCount = Result.Document.Interactions.Num();
    TSet<FString> ResourceIds;
    TMap<FString, FString> ResourceKinds;
    const FString DocumentDirectory = FPaths::GetPath(DocumentPath);
    for (const FTigerStudioUMGResourceRecord& Resource : Result.Document.Resources)
    {
        if (Resource.Id.IsEmpty() || ResourceIds.Contains(Resource.Id))
        {
            Result.Message = TEXT("Resource IDs must be non-empty and unique.");
            return Result;
        }
        ResourceIds.Add(Resource.Id);
        ResourceKinds.Add(Resource.Id, Resource.Kind);
        const FString SourcePath = FPaths::IsRelative(Resource.SourcePath)
            ? FPaths::ConvertRelativePathToFull(DocumentDirectory, Resource.SourcePath)
            : Resource.SourcePath;
        if (!FPaths::FileExists(SourcePath))
        {
            Result.Message = FString::Printf(
                TEXT("Resource file is missing: %s"),
                *SourcePath);
            return Result;
        }
    }

    TMap<FString, FString> ParentPanelKinds;
    TMap<FString, FString> ParentScrollOverflow;
    for (const FTigerStudioUMGLayerRecord& Layer : Result.Document.Layers)
    {
        if (Layer.Kind != ETigerStudioUMGLayerKind::Group)
        {
            continue;
        }
        ParentPanelKinds.Add(
            Layer.Id,
            (Layer.PanelKind.IsEmpty() || Layer.PanelKind == TEXT("None"))
                ? TEXT("Canvas")
                : Layer.PanelKind);
        ParentScrollOverflow.Add(
            Layer.Id,
            Layer.ScrollOverflow.IsEmpty()
                ? TEXT("None")
                : Layer.ScrollOverflow);
    }

    for (const FTigerStudioUMGLayerRecord& Layer : Result.Document.Layers)
    {
        if (Layer.Disposition == ETigerStudioUMGDisposition::Native)
        {
            for (const FString& Reason : ValidateImageFillLayer(
                     Layer,
                     Result.Document.SchemaVersion,
                     ResourceKinds,
                     ParentPanelKinds))
            {
                Result.BlockReasons.Add(Layer.Id + TEXT(":") + Reason);
            }
        }
        const FString ScrollOverflow = Layer.ScrollOverflow.IsEmpty()
            ? TEXT("None")
            : Layer.ScrollOverflow;
        const FString ScrollPosition = Layer.ScrollPosition.IsEmpty()
            ? TEXT("Scroll")
            : Layer.ScrollPosition;
        if (ScrollOverflow != TEXT("None")
            && ScrollOverflow != TEXT("Horizontal")
            && ScrollOverflow != TEXT("Vertical")
            && ScrollOverflow != TEXT("Both"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_scroll_overflow_unsupported:")
                + ScrollOverflow);
        }
        if (ScrollPosition != TEXT("Scroll")
            && ScrollPosition != TEXT("Fixed")
            && ScrollPosition != TEXT("Sticky"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_scroll_position_unsupported:")
                + ScrollPosition);
        }
        if (Result.Document.SchemaVersion < 10
            && (ScrollOverflow != TEXT("None")
                || ScrollPosition != TEXT("Scroll")))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_scroll_requires_schema_10"));
        }
        if (ScrollOverflow != TEXT("None")
            && Layer.Kind != ETigerStudioUMGLayerKind::Group)
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_scroll_overflow_requires_group"));
        }
        if (ScrollPosition == TEXT("Sticky"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_sticky_runtime_binding_unavailable"));
        }
        if (ScrollPosition == TEXT("Fixed"))
        {
            const FString* ParentOverflow =
                ParentScrollOverflow.Find(Layer.ParentId);
            if (!ParentOverflow || *ParentOverflow == TEXT("None"))
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_fixed_requires_scroll_parent"));
            }
        }
        if (Layer.Kind == ETigerStudioUMGLayerKind::Group)
        {
            const FString PanelKind = (
                Layer.PanelKind.IsEmpty() || Layer.PanelKind == TEXT("None"))
                ? TEXT("Canvas")
                : Layer.PanelKind;
            if (PanelKind != TEXT("Canvas")
                && PanelKind != TEXT("Horizontal")
                && PanelKind != TEXT("Vertical")
                && PanelKind != TEXT("Grid"))
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_panel_kind_unsupported:")
                    + PanelKind);
            }
            if (Result.Document.SchemaVersion < 7
                && PanelKind != TEXT("Canvas"))
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_flow_panel_requires_schema_7"));
            }
            if (Result.Document.SchemaVersion < 9
                && PanelKind == TEXT("Grid"))
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_grid_panel_requires_schema_9"));
            }
        }
        switch (Layer.Disposition)
        {
        case ETigerStudioUMGDisposition::Native:
            ++Result.NativeLayerCount;
            break;
        case ETigerStudioUMGDisposition::Material:
        {
            ++Result.MaterialLayerCount;
            const bool bRoundedCardMaterial =
                Layer.Material.Schema
                    == TEXT("tigerstudio.umg.ui_material.v2")
                || Layer.Material.Generator
                    == TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1")
                || Layer.Material.Kind == TEXT("RoundedCard");
            const int32 RequiredMaterialSchema =
                bRoundedCardMaterial ? 8 : 6;
            if (Result.Document.SchemaVersion < RequiredMaterialSchema)
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + FString::Printf(
                        TEXT(":ui_material_requires_schema_%d"),
                        RequiredMaterialSchema));
                break;
            }
            if (bRoundedCardMaterial
                && RoundedCardRequiresDynamicSizeBinding(
                    Layer,
                    ParentPanelKinds))
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + TEXT(
                        ":rounded_card_runtime_resize_requires_dynamic_size_binding"));
            }
            for (const FString& Reason : ValidateMaterialLayer(
                     Layer,
                     Result.Document.SchemaVersion))
            {
                Result.BlockReasons.Add(Layer.Id + TEXT(":") + Reason);
            }
            break;
        }
        case ETigerStudioUMGDisposition::Baked:
            ++Result.BakedLayerCount;
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":baked_generation_unavailable"));
            break;
        case ETigerStudioUMGDisposition::Blocked:
            ++Result.BlockedLayerCount;
            if (Layer.BlockReasons.IsEmpty())
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":unsupported_layer"));
            }
            else
            {
                for (const FString& Reason : Layer.BlockReasons)
                {
                    Result.BlockReasons.Add(
                        Layer.Id + TEXT(":") + Reason);
                }
            }
            break;
        default:
            break;
        }
    }

    if (!Result.BlockReasons.IsEmpty())
    {
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by unsupported generation layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }

    Result.bSuccess = true;
    Result.Message =
        TEXT("Tiger UMG document is ready for native/material generation.");
    return Result;
}
