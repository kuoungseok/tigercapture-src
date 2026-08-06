#include "TigerStudioUMGImportSubsystem.h"

#include "Animation/MovieScene2DTransformSection.h"
#include "Animation/MovieScene2DTransformTrack.h"
#include "Animation/WidgetAnimation.h"
#include "AssetImportTask.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetToolsModule.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ButtonSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/GridPanel.h"
#include "Components/GridSlot.h"
#include "Components/Image.h"
#include "Components/NamedSlot.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/PanelWidget.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/ScaleBox.h"
#include "Components/ScaleBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/Spacer.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/Widget.h"
#include "WidgetBlueprintFactory.h"
#include "IAssetTools.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "Factories/UIMaterialFactoryNew.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "EdGraphSchema_K2.h"
#include "MaterialEditingLibrary.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpressionComponentMask.h"
#include "Materials/MaterialExpressionCustom.h"
#include "Materials/MaterialExpressionScalarParameter.h"
#include "Materials/MaterialExpressionTextureSampleParameter2D.h"
#include "Materials/MaterialExpressionTextureCoordinate.h"
#include "Materials/MaterialExpressionTime.h"
#include "Materials/MaterialExpressionVectorParameter.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "MovieScene.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Styling/SlateBrush.h"
#include "Styling/SlateTypes.h"
#include "TextureCompiler.h"
#include "TigerStudioButton.h"
#include "TigerStudioComponentWidget.h"
#include "TigerStudioGeneratedWidget.h"
#include "TigerStudioRoundedCardHost.h"
#include "Tracks/MovieSceneFloatTrack.h"
#include "UObject/SavePackage.h"
#include "WidgetBlueprint.h"

namespace
{
FString SafeObjectName(const FString& Input)
{
    FString Result;
    for (const TCHAR Character : Input)
    {
        Result.AppendChar(
            FChar::IsAlnum(Character) || Character == TEXT('_')
                ? Character
                : TEXT('_'));
    }
    return Result.IsEmpty() ? TEXT("Document") : Result;
}

FName SafeComponentVariableName(const FString& Input)
{
    FString Result;
    for (const TCHAR Character : Input)
    {
        Result.AppendChar(
            FChar::IsAlnum(Character) || Character == TEXT('_')
                ? Character
                : TEXT('_'));
    }
    if (Result.IsEmpty() || FChar::IsDigit(Result[0]))
    {
        Result = TEXT("Property_") + Result;
    }
    return FName(*Result);
}

TSharedPtr<FJsonObject> ParsePayload(const FString& Payload)
{
    TSharedPtr<FJsonObject> Result;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Payload);
    FJsonSerializer::Deserialize(Reader, Result);
    return Result;
}

FLinearColor PayloadColor(
    const TSharedPtr<FJsonObject>& Payload,
    const TCHAR* Field,
    const FLinearColor& Fallback)
{
    FString Hex;
    if (!Payload || !Payload->TryGetStringField(Field, Hex))
    {
        return Fallback;
    }
    Hex.RemoveFromStart(TEXT("#"));
    return FLinearColor(FColor::FromHex(Hex));
}

FLinearColor ButtonStateColor(
    const FString& Value,
    const double Opacity)
{
    FString Hex = Value;
    Hex.RemoveFromStart(TEXT("#"));
    FLinearColor Result = FLinearColor(FColor::FromHex(Hex));
    Result.A *= static_cast<float>(Opacity);
    return Result;
}

FSlateBrush MakeButtonStateBrush(
    const FTigerStudioUMGButtonStateRecord& State,
    const FVector2D& LayerSize)
{
    return FSlateRoundedBoxBrush(
        ButtonStateColor(State.Fill, State.Opacity),
        State.CornerRadii,
        ButtonStateColor(State.Stroke, State.Opacity),
        static_cast<float>(State.StrokeWidth),
        FVector2f(
            static_cast<float>(FMath::Max(1.0, LayerSize.X)),
            static_cast<float>(FMath::Max(1.0, LayerSize.Y))));
}

FName ButtonTypefaceForWeight(const int32 FontWeight)
{
    if (FontWeight <= 200)
    {
        return FName(TEXT("VeryLight"));
    }
    if (FontWeight <= 300)
    {
        return FName(TEXT("Light"));
    }
    if (FontWeight <= 400)
    {
        return FName(TEXT("Regular"));
    }
    if (FontWeight <= 600)
    {
        return FName(TEXT("Medium"));
    }
    if (FontWeight <= 800)
    {
        return FName(TEXT("Bold"));
    }
    return FName(TEXT("Black"));
}

constexpr double TigerCssPixelsPerInch = 96.0;
constexpr double TigerPointsPerInch = 72.0;

FString PayloadFontSizeUnit(const TSharedPtr<FJsonObject>& Payload)
{
    FString Unit;
    if (Payload)
    {
        Payload->TryGetStringField(TEXT("font_size_unit"), Unit);
    }
    return Unit;
}

bool PayloadUsesCssPixelFontSize(const TSharedPtr<FJsonObject>& Payload)
{
    return PayloadFontSizeUnit(Payload).Equals(
        TEXT("css_px_96dpi"),
        ESearchCase::IgnoreCase);
}

float PayloadFontSizeInSlatePoints(
    const TSharedPtr<FJsonObject>& Payload,
    const double AuthoredSize)
{
    const double PointSize = PayloadUsesCssPixelFontSize(Payload)
        ? AuthoredSize * TigerPointsPerInch / TigerCssPixelsPerInch
        : AuthoredSize;
    // Payloads without an explicit unit are legacy/shared-provider records;
    // retain their previous native-Slate point interpretation.
    return static_cast<float>(FMath::Max(1.0, PointSize));
}

FString PayloadFontSizeUnitForAudit(
    const TSharedPtr<FJsonObject>& Payload)
{
    return PayloadUsesCssPixelFontSize(Payload)
        ? TEXT("css_px_96dpi")
        : TEXT("legacy_slate_points");
}

double SlatePointsToCssPixels96Dpi(const double PointSize)
{
    return PointSize * TigerCssPixelsPerInch / TigerPointsPerInch;
}

FButtonStyle MakeTypedButtonStyle(
    const FTigerStudioUMGButtonStyleRecord& Record,
    const FVector2D& LayerSize)
{
    FButtonStyle Style;
    Style
        .SetNormal(MakeButtonStateBrush(Record.Normal, LayerSize))
        .SetHovered(MakeButtonStateBrush(Record.Hovered, LayerSize))
        .SetPressed(MakeButtonStateBrush(Record.Pressed, LayerSize))
        .SetDisabled(MakeButtonStateBrush(Record.Disabled, LayerSize))
        .SetNormalForeground(FSlateColor(ButtonStateColor(
            Record.Normal.TextColor,
            Record.Normal.Opacity)))
        .SetHoveredForeground(FSlateColor(ButtonStateColor(
            Record.Hovered.TextColor,
            Record.Hovered.Opacity)))
        .SetPressedForeground(FSlateColor(ButtonStateColor(
            Record.Pressed.TextColor,
            Record.Pressed.Opacity)))
        .SetDisabledForeground(FSlateColor(ButtonStateColor(
            Record.Disabled.TextColor,
            Record.Disabled.Opacity)))
        .SetNormalPadding(FMargin(0.0))
        .SetPressedPadding(FMargin(0.0));
    return Style;
}

void ApplyTypedButtonLabelStyle(
    UTextBlock* Label,
    const FTigerStudioUMGButtonStyleRecord& Record,
    const float AppliedFontSize)
{
    if (!Label)
    {
        return;
    }
    FSlateFontInfo Font = Label->GetFont();
    Font.Size = FMath::Max(1.0f, AppliedFontSize);
    Font.TypefaceFontName = ButtonTypefaceForWeight(
        Record.Normal.FontWeight);
    Label->SetFont(Font);
    // SButton supplies the state-specific foreground color inherited by this
    // label; assigning a fixed color here would erase hover/press/disable.
    Label->SetColorAndOpacity(FSlateColor::UseForeground());
}

FString ButtonStyleAuditJson(
    const FTigerStudioUMGButtonStyleRecord& Record,
    const bool bImageFillBackground,
    const FString& AuthoredFontSizeUnit,
    const float AppliedLabelFontSize)
{
    const auto StateJson = [](const FTigerStudioUMGButtonStateRecord& State)
    {
        return FString::Printf(
            TEXT("{\"fill\":\"%s\",\"stroke\":\"%s\",\"stroke_width\":%.6g,")
            TEXT("\"radii\":[%.6g,%.6g,%.6g,%.6g],\"text\":\"%s\",")
            TEXT("\"font_size\":%.6g,\"font_weight\":%d,\"opacity\":%.6g}"),
            *State.Fill,
            *State.Stroke,
            State.StrokeWidth,
            State.CornerRadii.X,
            State.CornerRadii.Y,
            State.CornerRadii.Z,
            State.CornerRadii.W,
            *State.TextColor,
            State.FontSize,
            State.FontWeight,
            State.Opacity);
    };
    return FString::Printf(
        TEXT("{\"schema\":\"%s\",\"enabled\":%s,\"image_fill_background\":%s,")
        TEXT("\"label_font\":{\"authored_size\":%.6g,\"authored_unit\":\"%s\",")
        TEXT("\"applied_slate_points\":%.6g,\"display_css_px_96dpi\":%.6g},")
        TEXT("\"normal\":%s,\"hovered\":%s,\"pressed\":%s,\"disabled\":%s}"),
        *Record.Schema,
        Record.Enabled ? TEXT("true") : TEXT("false"),
        bImageFillBackground ? TEXT("true") : TEXT("false"),
        Record.Normal.FontSize,
        *AuthoredFontSizeUnit,
        AppliedLabelFontSize,
        SlatePointsToCssPixels96Dpi(AppliedLabelFontSize),
        *StateJson(Record.Normal),
        *StateJson(Record.Hovered),
        *StateJson(Record.Pressed),
        *StateJson(Record.Disabled));
}

bool HasImageFillCornerRadii(const FVector4& Radii)
{
    return Radii.X > 0.0001
        || Radii.Y > 0.0001
        || Radii.Z > 0.0001
        || Radii.W > 0.0001;
}

FVector2D ImageFillSourceSize(
    const FTigerStudioUMGImageFillRecord& ImageFill,
    const UTexture2D* Texture)
{
    if (ImageFill.SourceSize.X > 0.0 && ImageFill.SourceSize.Y > 0.0)
    {
        return ImageFill.SourceSize;
    }
    return Texture
        ? FVector2D(Texture->GetSizeX(), Texture->GetSizeY())
        : FVector2D(1.0, 1.0);
}

struct FImageFillSourceRegion
{
    FVector2D MinimumUV = FVector2D::ZeroVector;
    FVector2D MaximumUV = FVector2D(1.0, 1.0);
    FVector2D PixelSize = FVector2D(1.0, 1.0);
};

FImageFillSourceRegion ResolveImageFillSourceRegion(
    const FTigerStudioUMGImageFillRecord& ImageFill,
    const UTexture2D* Texture)
{
    FImageFillSourceRegion Result;
    const FVector2D SourceSize = ImageFillSourceSize(ImageFill, Texture);
    Result.PixelSize = SourceSize;
    if (!ImageFill.Crop.Enabled)
    {
        return Result;
    }

    const double ScaleX = ImageFill.Crop.Units == TEXT("Pixels")
        ? SourceSize.X
        : 1.0;
    const double ScaleY = ImageFill.Crop.Units == TEXT("Pixels")
        ? SourceSize.Y
        : 1.0;
    Result.MinimumUV = FVector2D(
        ImageFill.Crop.X / ScaleX,
        ImageFill.Crop.Y / ScaleY);
    Result.MaximumUV = FVector2D(
        (ImageFill.Crop.X + ImageFill.Crop.Width) / ScaleX,
        (ImageFill.Crop.Y + ImageFill.Crop.Height) / ScaleY);
    Result.PixelSize = FVector2D(
        SourceSize.X * (Result.MaximumUV.X - Result.MinimumUV.X),
        SourceSize.Y * (Result.MaximumUV.Y - Result.MinimumUV.Y));
    return Result;
}

FLinearColor ImageFillTint(
    const FTigerStudioUMGImageFillRecord& ImageFill)
{
    FString Hex = ImageFill.Tint;
    Hex.RemoveFromStart(TEXT("#"));
    FLinearColor Result = FLinearColor(FColor::FromHex(Hex));
    Result.A *= static_cast<float>(ImageFill.Opacity);
    return Result;
}

FSlateBrush MakeImageFillBrush(
    UTexture2D* Texture,
    const FTigerStudioUMGLayerRecord& Layer)
{
    const FTigerStudioUMGImageFillRecord& ImageFill = Layer.ImageFill;
    const FImageFillSourceRegion SourceRegion =
        ResolveImageFillSourceRegion(ImageFill, Texture);
    FSlateBrush Brush;
    Brush.SetResourceObject(Texture);
    Brush.SetImageSize(SourceRegion.PixelSize);
    Brush.DrawAs = ESlateBrushDrawType::Image;
    Brush.Tiling = ESlateBrushTileType::NoTile;
    Brush.ImageType = ESlateBrushImageType::FullColor;
    Brush.TintColor = FSlateColor(ImageFillTint(ImageFill));
    if (ImageFill.Crop.Enabled)
    {
        Brush.SetUVRegion(FBox2f(
            FVector2f(SourceRegion.MinimumUV),
            FVector2f(SourceRegion.MaximumUV)));
    }

    if (ImageFill.NineSlice.Enabled)
    {
        const double ScaleX = ImageFill.NineSlice.Units == TEXT("Pixels")
            ? SourceRegion.PixelSize.X
            : 1.0;
        const double ScaleY = ImageFill.NineSlice.Units == TEXT("Pixels")
            ? SourceRegion.PixelSize.Y
            : 1.0;
        Brush.DrawAs = ESlateBrushDrawType::Box;
        Brush.Margin = FMargin(
            ImageFill.NineSlice.Left / ScaleX,
            ImageFill.NineSlice.Top / ScaleY,
            ImageFill.NineSlice.Right / ScaleX,
            ImageFill.NineSlice.Bottom / ScaleY);
        return Brush;
    }

    if (ImageFill.Mode == TEXT("Fill"))
    {
        const FVector2D TargetSize(
            FMath::Max(0.0001, Layer.Size.X),
            FMath::Max(0.0001, Layer.Size.Y));
        const double Scale = FMath::Max(
            TargetSize.X / SourceRegion.PixelSize.X,
            TargetSize.Y / SourceRegion.PixelSize.Y);
        const double VisibleU = FMath::Clamp(
            TargetSize.X / Scale / SourceRegion.PixelSize.X,
            0.0,
            1.0);
        const double VisibleV = FMath::Clamp(
            TargetSize.Y / Scale / SourceRegion.PixelSize.Y,
            0.0,
            1.0);
        const double LocalMinimumU = FMath::Clamp(
            ImageFill.FocalPoint.X - VisibleU * 0.5,
            0.0,
            1.0 - VisibleU);
        const double LocalMinimumV = FMath::Clamp(
            ImageFill.FocalPoint.Y - VisibleV * 0.5,
            0.0,
            1.0 - VisibleV);
        const FVector2D BaseUVSize =
            SourceRegion.MaximumUV - SourceRegion.MinimumUV;
        const double MinimumU = SourceRegion.MinimumUV.X
            + LocalMinimumU * BaseUVSize.X;
        const double MinimumV = SourceRegion.MinimumUV.Y
            + LocalMinimumV * BaseUVSize.Y;
        const double MaximumU = MinimumU + VisibleU * BaseUVSize.X;
        const double MaximumV = MinimumV + VisibleV * BaseUVSize.Y;
        Brush.SetUVRegion(FBox2f(
            FVector2f(MinimumU, MinimumV),
            FVector2f(MaximumU, MaximumV)));
    }
    else if (ImageFill.Mode == TEXT("Tile"))
    {
        Brush.Tiling = ESlateBrushTileType::Both;
        Brush.SetImageSize(SourceRegion.PixelSize * ImageFill.TileScale);
    }

    if (HasImageFillCornerRadii(ImageFill.CornerRadii))
    {
        FVector4 EffectiveRadii = ImageFill.CornerRadii;
        if (ImageFill.Mode == TEXT("Fit"))
        {
            const double FitScale = FMath::Min(
                FMath::Max(0.0001, Layer.Size.X)
                    / SourceRegion.PixelSize.X,
                FMath::Max(0.0001, Layer.Size.Y)
                    / SourceRegion.PixelSize.Y);
            if (FitScale > 0.000001)
            {
                EffectiveRadii /= FitScale;
            }
        }
        Brush.DrawAs = ESlateBrushDrawType::RoundedBox;
        Brush.OutlineSettings = FSlateBrushOutlineSettings(EffectiveRadii);
    }
    return Brush;
}

UWidget* CreateImageFillWidget(
    UWidgetTree* WidgetTree,
    const FTigerStudioUMGLayerRecord& Layer,
    UTexture2D* Texture,
    const FName WidgetName)
{
    if (!WidgetTree || !Texture)
    {
        return nullptr;
    }
    const bool bFit = Layer.ImageFill.Mode == TEXT("Fit")
        && !Layer.ImageFill.NineSlice.Enabled;
    const FName ImageName = bFit
        ? FName(*(WidgetName.ToString() + TEXT("_Image")))
        : WidgetName;
    UImage* Image = WidgetTree->ConstructWidget<UImage>(
        UImage::StaticClass(),
        ImageName);
    Image->SetBrush(MakeImageFillBrush(Texture, Layer));
    Image->SetColorAndOpacity(FLinearColor::White);
    if (!bFit)
    {
        return Image;
    }

    Image->SetDesiredSizeOverride(ResolveImageFillSourceRegion(
        Layer.ImageFill,
        Texture).PixelSize);
    UScaleBox* ScaleBox = WidgetTree->ConstructWidget<UScaleBox>(
        UScaleBox::StaticClass(),
        WidgetName);
    ScaleBox->SetStretch(EStretch::ScaleToFit);
    ScaleBox->SetStretchDirection(EStretchDirection::Both);
    if (UScaleBoxSlot* Slot = Cast<UScaleBoxSlot>(ScaleBox->AddChild(Image)))
    {
        Slot->SetHorizontalAlignment(HAlign_Center);
        Slot->SetVerticalAlignment(VAlign_Center);
    }
    return ScaleBox;
}

void AddOverlayFill(UOverlay* Overlay, UWidget* Child)
{
    if (!Overlay || !Child)
    {
        return;
    }
    if (UOverlaySlot* Slot = Overlay->AddChildToOverlay(Child))
    {
        Slot->SetHorizontalAlignment(HAlign_Fill);
        Slot->SetVerticalAlignment(VAlign_Fill);
        Slot->SetPadding(FMargin(0.0));
    }
}

UTexture2D* LoadImageFillTexture(
    const FTigerStudioUMGLayerRecord& Layer,
    const TMap<FString, FSoftObjectPath>& ResourcePaths)
{
    if (Layer.ImageFill.AssetId.IsEmpty())
    {
        return nullptr;
    }
    const FSoftObjectPath* AssetPath =
        ResourcePaths.Find(Layer.ImageFill.AssetId);
    return AssetPath
        ? Cast<UTexture2D>(AssetPath->TryLoad())
        : nullptr;
}

UTexture2D* LoadFlipbookTexture(
    const FTigerStudioUMGLayerRecord& Layer,
    const TMap<FString, FSoftObjectPath>& ResourcePaths)
{
    if (Layer.Flipbook.AssetId.IsEmpty())
    {
        return nullptr;
    }
    const FSoftObjectPath* AssetPath =
        ResourcePaths.Find(Layer.Flipbook.AssetId);
    return AssetPath
        ? Cast<UTexture2D>(AssetPath->TryLoad())
        : nullptr;
}

void AddKey(
    FMovieSceneFloatChannel& Channel,
    const FTigerStudioUMGKeyframeRecord& Key,
    const float Value)
{
    const FFrameNumber Time(Key.TimeMilliseconds);
    const FString Interpolation = Key.Interpolation.ToLower();
    if (Interpolation == TEXT("constant") || Interpolation == TEXT("hold"))
    {
        Channel.AddConstantKey(Time, Value);
    }
    else if (Interpolation == TEXT("linear"))
    {
        Channel.AddLinearKey(Time, Value);
    }
    else
    {
        Channel.AddCubicKey(Time, Value);
    }
}

bool SaveAssetPackage(UObject* Asset)
{
    if (!Asset)
    {
        return false;
    }
    UPackage* Package = Asset->GetOutermost();
    const FString Filename = FPackageName::LongPackageNameToFilename(
        Package->GetName(),
        FPackageName::GetAssetPackageExtension());
    FSavePackageArgs Args;
    Args.TopLevelFlags = RF_Public | RF_Standalone;
    Args.SaveFlags = SAVE_NoError;
    return UPackage::SavePackage(Package, Asset, *Filename, Args);
}

FLinearColor MaterialColor(const FString& Value)
{
    FString Hex = Value;
    Hex.RemoveFromStart(TEXT("#"));
    return FLinearColor(FColor::FromHex(Hex));
}

void AddCustomInput(
    UMaterialExpressionCustom* Custom,
    const TCHAR* Name,
    UMaterialExpression* Expression,
    const int32 OutputIndex = 0)
{
    FCustomInput Input;
    Input.InputName = FName(Name);
    Input.Input.Connect(OutputIndex, Expression);
    Custom->Inputs.Add(Input);
}

FString GradientCustomHlsl(const FTigerStudioUMGMaterialRecord& Material)
{
    FString Code;
    if (Material.Kind == TEXT("RadialGradient"))
    {
        Code += TEXT(
            "float Radius = max(length(End.xy - Start.xy), 0.000001);\n"
            "float T = saturate(length(UV - Start.xy) / Radius);\n");
    }
    else
    {
        Code += TEXT(
            "float2 Axis = End.xy - Start.xy;\n"
            "float Denominator = max(dot(Axis, Axis), 0.000001);\n"
            "float T = saturate(dot(UV - Start.xy, Axis) / Denominator);\n");
    }
    Code += TEXT("float4 Result = Color0;\n");
    Code += FString::Printf(
        TEXT("if (T <= %.9g) Result = Color0;\n"),
        Material.Stops[0].Position);
    for (int32 Index = 1; Index < Material.Stops.Num(); ++Index)
    {
        const double Previous = Material.Stops[Index - 1].Position;
        const double Position = Material.Stops[Index].Position;
        const double Span = FMath::Max(0.000001, Position - Previous);
        Code += FString::Printf(
            TEXT(
                "else if (T <= %.9g) Result = lerp(Color%d, Color%d, "
                "saturate((T - %.9g) / %.9g));\n"),
            Position,
            Index - 1,
            Index,
            Previous,
            Span);
    }
    Code += FString::Printf(
        TEXT("else Result = Color%d;\n"),
        Material.Stops.Num() - 1);
    Code += TEXT(
        "Result.a *= saturate(FillOpacity);\n"
        "return Result;");
    return Code;
}

UMaterial* GenerateGradientMaterial(
    IAssetTools& AssetTools,
    const FString& GeneratedRoot,
    const FTigerStudioUMGLayerRecord& Layer,
    FTigerStudioUMGGenerationResult& Result)
{
    const FString MaterialPath = GeneratedRoot / TEXT("Materials");
    const FString MaterialName =
        TEXT("M_TS_") + SafeObjectName(Layer.Id);
    const FString ObjectPath = FString::Printf(
        TEXT("%s/%s.%s"),
        *MaterialPath,
        *MaterialName,
        *MaterialName);
    UMaterial* Material = LoadObject<UMaterial>(nullptr, *ObjectPath);
    if (!Material)
    {
        UUIMaterialFactoryNew* Factory = NewObject<UUIMaterialFactoryNew>();
        Material = Cast<UMaterial>(
            AssetTools.CreateAsset(
                MaterialName,
                MaterialPath,
                UMaterial::StaticClass(),
                Factory));
    }
    if (!Material)
    {
        Result.Errors.Add(
            FString::Printf(
                TEXT("Could not create UI Material for layer: %s"),
                *Layer.Id));
        return nullptr;
    }

    Material->Modify();
    // Delete from a stable copy. DeleteAllMaterialExpressions iterates the
    // live collection while removing from it, which can leave alternating
    // expressions behind on regeneration in UE 5.8.
    const TArray<UMaterialExpression*> ExistingExpressions =
        UMaterialEditingLibrary::GetMaterialExpressions(Material);
    for (UMaterialExpression* Expression : ExistingExpressions)
    {
        UMaterialEditingLibrary::DeleteMaterialExpression(
            Material,
            Expression);
    }
    Material->MaterialDomain = EMaterialDomain::MD_UI;
    Material->BlendMode = EBlendMode::BLEND_Translucent;
    // A generated asset can be reused after it was edited manually.  Reset
    // this graph-level switch so the explicit UI outputs below remain active.
    Material->bUseMaterialAttributes = false;

    UMaterialExpressionTextureCoordinate* UV = Cast<
        UMaterialExpressionTextureCoordinate>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionTextureCoordinate::StaticClass(),
            -900,
            -80));
    UMaterialExpressionVectorParameter* Start = Cast<
        UMaterialExpressionVectorParameter>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionVectorParameter::StaticClass(),
            -900,
            80));
    UMaterialExpressionVectorParameter* End = Cast<
        UMaterialExpressionVectorParameter>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionVectorParameter::StaticClass(),
            -900,
            210));
    UMaterialExpressionScalarParameter* FillOpacity = Cast<
        UMaterialExpressionScalarParameter>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionScalarParameter::StaticClass(),
            -900,
            340));
    UMaterialExpressionCustom* Custom = Cast<UMaterialExpressionCustom>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionCustom::StaticClass(),
            -300,
            60));
    UMaterialExpressionComponentMask* ColorMask = Cast<
        UMaterialExpressionComponentMask>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionComponentMask::StaticClass(),
            80,
            20));
    UMaterialExpressionComponentMask* AlphaMask = Cast<
        UMaterialExpressionComponentMask>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionComponentMask::StaticClass(),
            80,
            190));
    if (!UV || !Start || !End || !FillOpacity || !Custom
        || !ColorMask || !AlphaMask)
    {
        Result.Errors.Add(
            FString::Printf(
                TEXT("Could not create UI Material expressions for layer: %s"),
                *Layer.Id));
        return nullptr;
    }

    Start->ParameterName = TEXT("GradientStart");
    Start->Group = TEXT("Tiger Gradient");
    Start->SortPriority = 0;
    Start->DefaultValue = FLinearColor(
        Layer.Material.Start.X,
        Layer.Material.Start.Y,
        0.0,
        0.0);
    End->ParameterName = TEXT("GradientEnd");
    End->Group = TEXT("Tiger Gradient");
    End->SortPriority = 1;
    End->DefaultValue = FLinearColor(
        Layer.Material.End.X,
        Layer.Material.End.Y,
        0.0,
        0.0);
    FillOpacity->ParameterName = TEXT("FillOpacity");
    FillOpacity->Group = TEXT("Tiger Gradient");
    FillOpacity->SortPriority = 2;
    FillOpacity->DefaultValue = FMath::Clamp(
        static_cast<float>(Layer.Material.Opacity),
        0.0f,
        1.0f);

    AddCustomInput(Custom, TEXT("UV"), UV);
    AddCustomInput(Custom, TEXT("Start"), Start);
    AddCustomInput(Custom, TEXT("End"), End);
    AddCustomInput(Custom, TEXT("FillOpacity"), FillOpacity);
    for (int32 Index = 0; Index < Layer.Material.Stops.Num(); ++Index)
    {
        UMaterialExpressionVectorParameter* Color = Cast<
            UMaterialExpressionVectorParameter>(
            UMaterialEditingLibrary::CreateMaterialExpression(
                Material,
                UMaterialExpressionVectorParameter::StaticClass(),
                -650,
                420 + Index * 120));
        if (!Color)
        {
            Result.Errors.Add(
                FString::Printf(
                    TEXT("Could not create gradient color %d for layer: %s"),
                    Index,
                    *Layer.Id));
            return nullptr;
        }
        Color->ParameterName = FName(*FString::Printf(TEXT("Color%d"), Index));
        Color->Group = TEXT("Tiger Gradient");
        Color->SortPriority = 10 + Index;
        Color->DefaultValue = MaterialColor(
            Layer.Material.Stops[Index].Color);
        AddCustomInput(
            Custom,
            *FString::Printf(TEXT("Color%d"), Index),
            Color,
            5);
    }

    Custom->Description = TEXT("Tiger UI Gradient / validated Custom HLSL");
    Custom->OutputType = ECustomMaterialOutputType::CMOT_Float4;
    Custom->ContainsClipInstruction =
        ECustomMaterialClipInstruction::CMCI_No;
    Custom->Code = GradientCustomHlsl(Layer.Material);
    Custom->RebuildOutputs();

    ColorMask->R = true;
    ColorMask->G = true;
    ColorMask->B = true;
    ColorMask->A = false;
    AlphaMask->R = false;
    AlphaMask->G = false;
    AlphaMask->B = false;
    AlphaMask->A = true;
    const bool bColorMaskConnected =
        UMaterialEditingLibrary::ConnectMaterialExpressions(
            Custom,
            TEXT(""),
            ColorMask,
            TEXT(""));
    const bool bAlphaMaskConnected =
        UMaterialEditingLibrary::ConnectMaterialExpressions(
            Custom,
            TEXT(""),
            AlphaMask,
            TEXT(""));
    const bool bColorOutputConnected =
        UMaterialEditingLibrary::ConnectMaterialProperty(
            ColorMask,
            TEXT(""),
            EMaterialProperty::MP_EmissiveColor);
    const bool bOpacityOutputConnected =
        UMaterialEditingLibrary::ConnectMaterialProperty(
            AlphaMask,
            TEXT(""),
            EMaterialProperty::MP_Opacity);
    if (!bColorMaskConnected
        || !bAlphaMaskConnected
        || !bColorOutputConnected
        || !bOpacityOutputConnected)
    {
        Result.Errors.Add(
            FString::Printf(
                TEXT("Could not connect UI Material expressions for layer: %s"),
                *Layer.Id));
        return nullptr;
    }

    // RecompileMaterial performs the required PreEditChange/PostEditChange
    // cycle; calling PostEditChange separately would compile the asset twice.
    const TArray<FString> CompileErrors =
        UMaterialEditingLibrary::RecompileMaterial(Material);
    for (const FString& CompileError : CompileErrors)
    {
        Result.Errors.Add(
            FString::Printf(
                TEXT("%s:%s"),
                *Layer.Id,
                *CompileError));
    }
    if (!CompileErrors.IsEmpty())
    {
        return nullptr;
    }
    Material->MarkPackageDirty();
    if (!SaveAssetPackage(Material))
    {
        Result.Errors.Add(
            FString::Printf(
                TEXT("Generated UI Material could not be saved: %s"),
                *ObjectPath));
        return nullptr;
    }
    UE_LOG(
        LogTemp,
        Display,
        TEXT("TigerStudioUMG: saved generated UI Material %s"),
        *ObjectPath);
    Result.GeneratedMaterialPaths.AddUnique(ObjectPath);
    return Material;
}

FString FlipbookCustomHlsl()
{
    return TEXT(
        "// Tiger Flipbook Atlas / validated fixed Custom HLSL\n"
        "float SafeColumns = max(floor(Columns + 0.5), 1.0);\n"
        "float SafeRows = max(floor(Rows + 0.5), 1.0);\n"
        "float Capacity = SafeColumns * SafeRows;\n"
        "float SafeFrameCount = clamp(floor(FrameCount + 0.5), 1.0, Capacity);\n"
        "float SafeStartFrame = clamp(floor(StartFrame + 0.5), 0.0, SafeFrameCount - 1.0);\n"
        "float PhaseOffset = floor(saturate(Phase) * SafeFrameCount);\n"
        "float AnimatedOffset = floor(max(TimeSeconds, 0.0) * max(FramesPerSecond, 0.0));\n"
        "float FrameOffset = (StaticFrameOverride >= 0.0) ? floor(StaticFrameOverride + 0.5) : (PhaseOffset + AnimatedOffset);\n"
        "float RawFrame = SafeStartFrame + FrameOffset;\n"
        "float SelectedFrame = (Loop >= 0.5) ? fmod(RawFrame, SafeFrameCount) : min(RawFrame, SafeFrameCount - 1.0);\n"
        "float Column = fmod(SelectedFrame, SafeColumns);\n"
        "float Row = floor(SelectedFrame / SafeColumns);\n"
        "float2 CellUV = min(saturate(UV), float2(0.999999, 0.999999));\n"
        "return (CellUV + float2(Column, Row)) / float2(SafeColumns, SafeRows);");
}

UMaterial* GenerateFlipbookMaterial(
    IAssetTools& AssetTools,
    const FString& GeneratedRoot,
    const FTigerStudioUMGLayerRecord& Layer,
    UTexture2D* AtlasTexture,
    FTigerStudioUMGGenerationResult& Result)
{
    if (!AtlasTexture)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Flipbook atlas texture could not be loaded: %s"),
            *Layer.Flipbook.AssetId));
        return nullptr;
    }

    const FString MaterialPath = GeneratedRoot / TEXT("Materials");
    const FString MaterialName = TEXT("M_TS_") + SafeObjectName(Layer.Id);
    const FString ObjectPath = FString::Printf(
        TEXT("%s/%s.%s"),
        *MaterialPath,
        *MaterialName,
        *MaterialName);
    UMaterial* Material = LoadObject<UMaterial>(nullptr, *ObjectPath);
    if (!Material)
    {
        UUIMaterialFactoryNew* Factory = NewObject<UUIMaterialFactoryNew>();
        Material = Cast<UMaterial>(AssetTools.CreateAsset(
            MaterialName,
            MaterialPath,
            UMaterial::StaticClass(),
            Factory));
    }
    if (!Material)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Could not create flipbook UI Material for layer: %s"),
            *Layer.Id));
        return nullptr;
    }

    Material->Modify();
    const TArray<UMaterialExpression*> ExistingExpressions =
        UMaterialEditingLibrary::GetMaterialExpressions(Material);
    for (UMaterialExpression* Expression : ExistingExpressions)
    {
        UMaterialEditingLibrary::DeleteMaterialExpression(
            Material,
            Expression);
    }
    Material->MaterialDomain = EMaterialDomain::MD_UI;
    Material->BlendMode = EBlendMode::BLEND_Translucent;
    Material->bUseMaterialAttributes = false;

    UMaterialExpressionTextureCoordinate* UV = Cast<
        UMaterialExpressionTextureCoordinate>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionTextureCoordinate::StaticClass(),
            -1200,
            -180));
    UMaterialExpressionTime* Time = Cast<UMaterialExpressionTime>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionTime::StaticClass(),
            -1200,
            -40));
    UMaterialExpressionCustom* Custom = Cast<UMaterialExpressionCustom>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionCustom::StaticClass(),
            -300,
            20));
    UMaterialExpressionTextureSampleParameter2D* TextureSample = Cast<
        UMaterialExpressionTextureSampleParameter2D>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionTextureSampleParameter2D::StaticClass(),
            40,
            20));
    if (!UV || !Time || !Custom || !TextureSample)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Could not create flipbook expressions for layer: %s"),
            *Layer.Id));
        return nullptr;
    }

    AddCustomInput(Custom, TEXT("UV"), UV);
    AddCustomInput(Custom, TEXT("TimeSeconds"), Time);
    int32 SortPriority = 0;
    int32 GraphY = 120;
    const auto AddScalarParameter = [
        &Material,
        &Custom,
        &SortPriority,
        &GraphY](
            const TCHAR* Name,
            const float DefaultValue) -> bool
    {
        UMaterialExpressionScalarParameter* Parameter = Cast<
            UMaterialExpressionScalarParameter>(
            UMaterialEditingLibrary::CreateMaterialExpression(
                Material,
                UMaterialExpressionScalarParameter::StaticClass(),
                -900,
                GraphY));
        GraphY += 100;
        if (!Parameter)
        {
            return false;
        }
        Parameter->ParameterName = FName(Name);
        Parameter->Group = TEXT("Tiger Flipbook");
        Parameter->SortPriority = SortPriority++;
        Parameter->DefaultValue = DefaultValue;
        AddCustomInput(Custom, Name, Parameter);
        return true;
    };

    const FTigerStudioUMGFlipbookRecord& Record = Layer.Flipbook;
    bool bParametersValid = true;
    bParametersValid &= AddScalarParameter(
        TEXT("Columns"), static_cast<float>(Record.Columns));
    bParametersValid &= AddScalarParameter(
        TEXT("Rows"), static_cast<float>(Record.Rows));
    bParametersValid &= AddScalarParameter(
        TEXT("FrameCount"), static_cast<float>(Record.FrameCount));
    bParametersValid &= AddScalarParameter(
        TEXT("FramesPerSecond"),
        static_cast<float>(Record.FramesPerSecond));
    bParametersValid &= AddScalarParameter(
        TEXT("StartFrame"), static_cast<float>(Record.StartFrame));
    bParametersValid &= AddScalarParameter(
        TEXT("Loop"), Record.Loop ? 1.0f : 0.0f);
    bParametersValid &= AddScalarParameter(
        TEXT("Phase"), static_cast<float>(Record.Phase));
    bParametersValid &= AddScalarParameter(
        TEXT("StaticFrameOverride"),
        static_cast<float>(Record.StaticFrameOverride));
    if (!bParametersValid)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Could not create flipbook parameters for layer: %s"),
            *Layer.Id));
        return nullptr;
    }

    Custom->Description =
        TEXT("Tiger Flipbook Atlas / validated fixed Custom HLSL");
    Custom->OutputType = ECustomMaterialOutputType::CMOT_Float2;
    Custom->ContainsClipInstruction =
        ECustomMaterialClipInstruction::CMCI_No;
    Custom->Code = FlipbookCustomHlsl();
    Custom->RebuildOutputs();

    TextureSample->ParameterName = TEXT("AtlasTexture");
    TextureSample->Group = TEXT("Tiger Flipbook");
    TextureSample->SortPriority = SortPriority++;
    TextureSample->Texture = AtlasTexture;
    TextureSample->SamplerType = SAMPLERTYPE_Color;

    // UE 5.8 exposes this input as "Coordinates" through GetInputName, but
    // MaterialEditingLibrary can still reject the name while the custom node
    // outputs float2. Connect the engine-owned FExpressionInput directly.
    TextureSample->Coordinates.Connect(0, Custom);
    const bool bCustomToTexture =
        TextureSample->Coordinates.Expression == Custom;
    // TextureSample output 0 is RGB (float3), not RGBA. Connect the explicit
    // named outputs straight to the UI properties; routing the unnamed RGB
    // output through an alpha component mask produces a failed shader map.
    const bool bTextureRgbToEmissive =
        UMaterialEditingLibrary::ConnectMaterialProperty(
            TextureSample,
            TEXT("RGB"),
            EMaterialProperty::MP_EmissiveColor);
    const bool bTextureAlphaToOpacity =
        UMaterialEditingLibrary::ConnectMaterialProperty(
            TextureSample,
            TEXT("A"),
            EMaterialProperty::MP_Opacity);
    if (!bCustomToTexture
        || !bTextureRgbToEmissive
        || !bTextureAlphaToOpacity)
    {
        Result.Errors.Add(FString::Printf(
            TEXT(
                "Could not connect flipbook expressions for layer %s "
                "[CustomToTexture=%d TextureRgbToEmissive=%d "
                "TextureAlphaToOpacity=%d]"),
            *Layer.Id,
            bCustomToTexture ? 1 : 0,
            bTextureRgbToEmissive ? 1 : 0,
            bTextureAlphaToOpacity ? 1 : 0));
        return nullptr;
    }

    const TArray<FString> CompileErrors =
        UMaterialEditingLibrary::RecompileMaterial(Material);
    for (const FString& CompileError : CompileErrors)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("%s:%s"),
            *Layer.Id,
            *CompileError));
    }
    if (!CompileErrors.IsEmpty())
    {
        return nullptr;
    }
    Material->MarkPackageDirty();
    if (!SaveAssetPackage(Material))
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Generated flipbook UI Material could not be saved: %s"),
            *ObjectPath));
        return nullptr;
    }
    Result.GeneratedMaterialPaths.AddUnique(ObjectPath);
    return Material;
}

void AppendRoundedDistanceHlsl(
    FString& Code,
    const TCHAR* Prefix,
    const TCHAR* PointExpression)
{
    // Keep the format calls deliberately small. UE's compile-time format
    // checker validates each FString::Printf invocation and a single long
    // expression is unnecessarily fragile when another SDF term is added.
    Code += FString::Printf(
        TEXT("float2 %sP = %s;\n"),
        Prefix,
        PointExpression);
    Code += FString::Printf(
        TEXT(
            "float %sRadius = (%sP.x < 0.0) "
            "? ((%sP.y < 0.0) ? EffectiveCornerRadii.x : EffectiveCornerRadii.w) "
            ": ((%sP.y < 0.0) ? EffectiveCornerRadii.y : EffectiveCornerRadii.z);\n"),
        Prefix,
        Prefix,
        Prefix,
        Prefix);
    Code += FString::Printf(
        TEXT(
            "float2 %sQ = abs(%sP) - max(CardSize.xy * 0.5 "
            "- float2(%sRadius, %sRadius), float2(0.0, 0.0));\n"),
        Prefix,
        Prefix,
        Prefix,
        Prefix);
    Code += FString::Printf(
        TEXT("float2 %sOutside = max(%sQ, float2(0.0, 0.0));\n"),
        Prefix,
        Prefix);
    Code += FString::Printf(
        TEXT(
            "float %sPower = lerp(2.0, 4.0, "
            "saturate(CornerSmoothing));\n"),
        Prefix);
    Code += FString::Printf(
        TEXT(
            "float %sCurve = pow(pow(%sOutside.x, %sPower) + "
            "pow(%sOutside.y, %sPower), 1.0 / %sPower);\n"),
        Prefix,
        Prefix,
        Prefix,
        Prefix,
        Prefix,
        Prefix);
    Code += FString::Printf(
        TEXT(
            "float %sDistance = %sCurve + min(max(%sQ.x, %sQ.y), "
            "0.0) - %sRadius;\n"),
        Prefix,
        Prefix,
        Prefix,
        Prefix,
        Prefix);
}

FString RoundedCardCustomHlsl(const FTigerStudioUMGMaterialRecord& Material)
{
    FString Code = TEXT(
        "float2 SurfaceSize = max(CardSize.xy + float2(VisualPadding.x + VisualPadding.z, VisualPadding.y + VisualPadding.w), float2(1.0, 1.0));\n"
        "float2 PixelPosition = UV * SurfaceSize - VisualPadding.xy;\n"
        "float2 CardUV = saturate(PixelPosition / max(CardSize.xy, float2(0.000001, 0.000001)));\n"
        "float2 CardPoint = PixelPosition - CardSize.xy * 0.5;\n"
        "float RadiusScaleX = CardSize.x / max(max(CornerRadii.x + CornerRadii.y, CornerRadii.w + CornerRadii.z), 0.000001);\n"
        "float RadiusScaleY = CardSize.y / max(max(CornerRadii.x + CornerRadii.w, CornerRadii.y + CornerRadii.z), 0.000001);\n"
        "float4 EffectiveCornerRadii = CornerRadii * min(1.0, min(RadiusScaleX, RadiusScaleY));\n");
    AppendRoundedDistanceHlsl(Code, TEXT("Base"), TEXT("CardPoint"));
    AppendRoundedDistanceHlsl(
        Code,
        TEXT("Drop"),
        TEXT("CardPoint - DropShadowOffset.xy"));
    AppendRoundedDistanceHlsl(
        Code,
        TEXT("Inner"),
        TEXT("CardPoint - InnerShadowOffset.xy"));

    if (Material.FillKind.Equals(
            TEXT("RadialGradient"),
            ESearchCase::IgnoreCase))
    {
        Code += TEXT(
            "float2 GradientBasisX = GradientEnd.xy - GradientStart.xy;\n"
            "float2 GradientBasisY = GradientWidth.xy - GradientStart.xy;\n"
            "float GradientDeterminant = GradientBasisX.x * GradientBasisY.y - GradientBasisX.y * GradientBasisY.x;\n"
            "float SafeGradientDeterminant = (abs(GradientDeterminant) < 0.000001) ? ((GradientDeterminant < 0.0) ? -0.000001 : 0.000001) : GradientDeterminant;\n"
            "float2 GradientDelta = CardUV - GradientStart.xy;\n"
            "float2 GradientLocal = float2((GradientDelta.x * GradientBasisY.y - GradientDelta.y * GradientBasisY.x) / SafeGradientDeterminant, (GradientBasisX.x * GradientDelta.y - GradientBasisX.y * GradientDelta.x) / SafeGradientDeterminant);\n"
            "float GradientT = saturate(length(GradientLocal));\n");
    }
    else if (Material.FillKind.Equals(
                 TEXT("LinearGradient"),
                 ESearchCase::IgnoreCase))
    {
        Code += TEXT(
            "float2 GradientAxis = GradientEnd.xy - GradientStart.xy;\n"
            "float GradientDenominator = max(dot(GradientAxis, GradientAxis), 0.000001);\n"
            "float GradientT = saturate(dot(CardUV - GradientStart.xy, GradientAxis) / GradientDenominator);\n");
    }

    if (Material.FillKind.Equals(
            TEXT("Solid"),
            ESearchCase::IgnoreCase))
    {
        Code += TEXT("float4 Fill = FillColor;\n");
    }
    else
    {
        Code += TEXT("float4 Fill = Color0;\n");
        Code += FString::Printf(
            TEXT("if (GradientT <= %.9g) Fill = Color0;\n"),
            Material.Stops[0].Position);
        for (int32 Index = 1; Index < Material.Stops.Num(); ++Index)
        {
            const double Previous = Material.Stops[Index - 1].Position;
            const double Position = Material.Stops[Index].Position;
            const double Span = FMath::Max(0.000001, Position - Previous);
            Code += FString::Printf(
                TEXT(
                    "else if (GradientT <= %.9g) Fill = lerp(Color%d, Color%d, "
                    "saturate((GradientT - %.9g) / %.9g));\n"),
                Position,
                Index - 1,
                Index,
                Previous,
                Span);
        }
        Code += FString::Printf(
            TEXT("else Fill = Color%d;\n"),
            Material.Stops.Num() - 1);
    }

    Code += TEXT(
        "float BaseAA = max(fwidth(BaseDistance), 0.75);\n"
        "float ShapeMask = 1.0 - smoothstep(-BaseAA, BaseAA, BaseDistance);\n"
        "float Alignment = clamp(StrokeAlignment, 0.0, 2.0);\n"
        "float OuterOffset = (Alignment < 0.5) ? 0.0 : ((Alignment < 1.5) ? StrokeWidth * 0.5 : StrokeWidth);\n"
        "float InnerOffset = (Alignment < 0.5) ? StrokeWidth : ((Alignment < 1.5) ? StrokeWidth * 0.5 : 0.0);\n"
        "float StrokeOuter = 1.0 - smoothstep(-BaseAA, BaseAA, BaseDistance - OuterOffset);\n"
        "float StrokeInner = 1.0 - smoothstep(-BaseAA, BaseAA, BaseDistance + InnerOffset);\n"
        "float StrokeMask = saturate(StrokeOuter - StrokeInner) * step(0.0001, StrokeWidth);\n"
        "Fill.a *= saturate(FillOpacity) * ShapeMask;\n"
        "float3 BasePremultiplied = Fill.rgb * Fill.a;\n"
        "float BaseAlpha = Fill.a;\n"
        "float StrokeAlpha = StrokeColor.a * StrokeMask;\n"
        "BasePremultiplied = StrokeColor.rgb * StrokeAlpha + BasePremultiplied * (1.0 - StrokeAlpha);\n"
        "BaseAlpha = StrokeAlpha + BaseAlpha * (1.0 - StrokeAlpha);\n"
        "float DropAA = max(fwidth(DropDistance), 0.75);\n"
        "float DropSoftness = max(DropShadowBlur, DropAA);\n"
        "float DropMask = (1.0 - smoothstep(-DropSoftness, DropSoftness, DropDistance - DropShadowSpread)) * saturate(DropShadowEnabled);\n"
        "float DropAlpha = DropShadowColor.a * DropMask;\n"
        "float3 AccumulatedRGB = DropShadowColor.rgb * DropAlpha;\n"
        "float AccumulatedAlpha = DropAlpha;\n"
        "AccumulatedRGB = BasePremultiplied + AccumulatedRGB * (1.0 - BaseAlpha);\n"
        "AccumulatedAlpha = BaseAlpha + AccumulatedAlpha * (1.0 - BaseAlpha);\n"
        "float InnerAA = max(fwidth(InnerDistance), 0.75);\n"
        "float InnerSoftness = max(InnerShadowBlur, InnerAA);\n"
        "float InnerMask = smoothstep(-InnerSoftness, InnerSoftness, InnerDistance + InnerShadowSpread) * ShapeMask * saturate(InnerShadowEnabled);\n"
        "float InnerAlpha = InnerShadowColor.a * InnerMask;\n"
        "AccumulatedRGB = InnerShadowColor.rgb * InnerAlpha + AccumulatedRGB * (1.0 - InnerAlpha);\n"
        "AccumulatedAlpha = InnerAlpha + AccumulatedAlpha * (1.0 - InnerAlpha);\n"
        "float3 ResultRGB = (AccumulatedAlpha > 0.00001) ? (AccumulatedRGB / AccumulatedAlpha) : float3(0.0, 0.0, 0.0);\n"
        "return float4(ResultRGB, saturate(AccumulatedAlpha));");
    return Code;
}

UMaterial* GenerateRoundedCardMaterial(
    IAssetTools& AssetTools,
    const FString& GeneratedRoot,
    const FTigerStudioUMGLayerRecord& Layer,
    FTigerStudioUMGGenerationResult& Result)
{
    const FString MaterialPath = GeneratedRoot / TEXT("Materials");
    const FString MaterialName = TEXT("M_TS_") + SafeObjectName(Layer.Id);
    const FString ObjectPath = FString::Printf(
        TEXT("%s/%s.%s"),
        *MaterialPath,
        *MaterialName,
        *MaterialName);
    UMaterial* Material = LoadObject<UMaterial>(nullptr, *ObjectPath);
    if (!Material)
    {
        UUIMaterialFactoryNew* Factory = NewObject<UUIMaterialFactoryNew>();
        Material = Cast<UMaterial>(
            AssetTools.CreateAsset(
                MaterialName,
                MaterialPath,
                UMaterial::StaticClass(),
                Factory));
    }
    if (!Material)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Could not create rounded-card UI Material for layer: %s"),
            *Layer.Id));
        return nullptr;
    }

    Material->Modify();
    const TArray<UMaterialExpression*> ExistingExpressions =
        UMaterialEditingLibrary::GetMaterialExpressions(Material);
    for (UMaterialExpression* Expression : ExistingExpressions)
    {
        UMaterialEditingLibrary::DeleteMaterialExpression(Material, Expression);
    }
    Material->MaterialDomain = EMaterialDomain::MD_UI;
    Material->BlendMode = EBlendMode::BLEND_Translucent;
    Material->bUseMaterialAttributes = false;

    UMaterialExpressionTextureCoordinate* UV = Cast<
        UMaterialExpressionTextureCoordinate>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionTextureCoordinate::StaticClass(),
            -1150,
            -120));
    UMaterialExpressionCustom* Custom = Cast<UMaterialExpressionCustom>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionCustom::StaticClass(),
            -260,
            80));
    UMaterialExpressionComponentMask* ColorMask = Cast<
        UMaterialExpressionComponentMask>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionComponentMask::StaticClass(),
            100,
            20));
    UMaterialExpressionComponentMask* AlphaMask = Cast<
        UMaterialExpressionComponentMask>(
        UMaterialEditingLibrary::CreateMaterialExpression(
            Material,
            UMaterialExpressionComponentMask::StaticClass(),
            100,
            190));
    if (!UV || !Custom || !ColorMask || !AlphaMask)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Could not create rounded-card expressions for layer: %s"),
            *Layer.Id));
        return nullptr;
    }
    AddCustomInput(Custom, TEXT("UV"), UV);

    int32 SortPriority = 0;
    int32 GraphY = 20;
    const auto AddVectorParameter = [&Material, &Custom, &SortPriority, &GraphY](
        const TCHAR* Name,
        const FLinearColor& DefaultValue,
        const TCHAR* Group) -> UMaterialExpressionVectorParameter*
    {
        UMaterialExpressionVectorParameter* Parameter = Cast<
            UMaterialExpressionVectorParameter>(
            UMaterialEditingLibrary::CreateMaterialExpression(
                Material,
                UMaterialExpressionVectorParameter::StaticClass(),
                -900,
                GraphY));
        GraphY += 110;
        if (Parameter)
        {
            Parameter->ParameterName = FName(Name);
            Parameter->Group = FName(Group);
            Parameter->SortPriority = SortPriority++;
            Parameter->DefaultValue = DefaultValue;
            AddCustomInput(Custom, Name, Parameter, 5);
        }
        return Parameter;
    };
    const auto AddScalarParameter = [&Material, &Custom, &SortPriority, &GraphY](
        const TCHAR* Name,
        const float DefaultValue,
        const TCHAR* Group) -> UMaterialExpressionScalarParameter*
    {
        UMaterialExpressionScalarParameter* Parameter = Cast<
            UMaterialExpressionScalarParameter>(
            UMaterialEditingLibrary::CreateMaterialExpression(
                Material,
                UMaterialExpressionScalarParameter::StaticClass(),
                -650,
                GraphY));
        GraphY += 110;
        if (Parameter)
        {
            Parameter->ParameterName = FName(Name);
            Parameter->Group = FName(Group);
            Parameter->SortPriority = SortPriority++;
            Parameter->DefaultValue = DefaultValue;
            AddCustomInput(Custom, Name, Parameter);
        }
        return Parameter;
    };

    const FTigerStudioUMGMaterialRecord& Record = Layer.Material;
    const float StrokeAlignment = Record.Stroke.Alignment.Equals(
        TEXT("Outside"), ESearchCase::IgnoreCase)
        ? 2.0f
        : Record.Stroke.Alignment.Equals(
              TEXT("Center"), ESearchCase::IgnoreCase)
            ? 1.0f
            : 0.0f;
    bool bParametersValid = true;
    bParametersValid &= AddVectorParameter(
        TEXT("CardSize"),
        FLinearColor(Record.Size.X, Record.Size.Y, 0.0, 0.0),
        TEXT("Tiger Rounded Card")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("VisualPadding"),
        FLinearColor(
            Record.VisualPadding.Left,
            Record.VisualPadding.Top,
            Record.VisualPadding.Right,
            Record.VisualPadding.Bottom),
        TEXT("Tiger Rounded Card")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("CornerRadii"),
        FLinearColor(
            Record.CornerRadii.X,
            Record.CornerRadii.Y,
            Record.CornerRadii.Z,
            Record.CornerRadii.W),
        TEXT("Tiger Rounded Card")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("CornerSmoothing"),
        static_cast<float>(Record.CornerSmoothing),
        TEXT("Tiger Rounded Card")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("FillColor"),
        MaterialColor(Record.FillColor),
        TEXT("Tiger Fill")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("GradientStart"),
        FLinearColor(Record.Start.X, Record.Start.Y, 0.0, 0.0),
        TEXT("Tiger Fill")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("GradientEnd"),
        FLinearColor(Record.End.X, Record.End.Y, 0.0, 0.0),
        TEXT("Tiger Fill")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("GradientWidth"),
        FLinearColor(Record.Width.X, Record.Width.Y, 0.0, 0.0),
        TEXT("Tiger Fill")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("FillOpacity"),
        static_cast<float>(Record.Opacity),
        TEXT("Tiger Fill")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("StrokeWidth"),
        static_cast<float>(Record.Stroke.Width),
        TEXT("Tiger Stroke")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("StrokeAlignment"),
        StrokeAlignment,
        TEXT("Tiger Stroke")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("StrokeColor"),
        MaterialColor(Record.Stroke.Color),
        TEXT("Tiger Stroke")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("DropShadowEnabled"),
        Record.DropShadow.Enabled ? 1.0f : 0.0f,
        TEXT("Tiger Drop Shadow")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("DropShadowColor"),
        MaterialColor(Record.DropShadow.Color),
        TEXT("Tiger Drop Shadow")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("DropShadowOffset"),
        FLinearColor(
            Record.DropShadow.Offset.X,
            Record.DropShadow.Offset.Y,
            0.0,
            0.0),
        TEXT("Tiger Drop Shadow")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("DropShadowBlur"),
        static_cast<float>(Record.DropShadow.Blur),
        TEXT("Tiger Drop Shadow")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("DropShadowSpread"),
        static_cast<float>(Record.DropShadow.Spread),
        TEXT("Tiger Drop Shadow")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("InnerShadowEnabled"),
        Record.InnerShadow.Enabled ? 1.0f : 0.0f,
        TEXT("Tiger Inner Shadow")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("InnerShadowColor"),
        MaterialColor(Record.InnerShadow.Color),
        TEXT("Tiger Inner Shadow")) != nullptr;
    bParametersValid &= AddVectorParameter(
        TEXT("InnerShadowOffset"),
        FLinearColor(
            Record.InnerShadow.Offset.X,
            Record.InnerShadow.Offset.Y,
            0.0,
            0.0),
        TEXT("Tiger Inner Shadow")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("InnerShadowBlur"),
        static_cast<float>(Record.InnerShadow.Blur),
        TEXT("Tiger Inner Shadow")) != nullptr;
    bParametersValid &= AddScalarParameter(
        TEXT("InnerShadowSpread"),
        static_cast<float>(Record.InnerShadow.Spread),
        TEXT("Tiger Inner Shadow")) != nullptr;

    if (!Record.FillKind.Equals(TEXT("Solid"), ESearchCase::IgnoreCase))
    {
        for (int32 Index = 0; Index < Record.Stops.Num(); ++Index)
        {
            const FString ParameterName = FString::Printf(
                TEXT("Color%d"),
                Index);
            bParametersValid &= AddVectorParameter(
                *ParameterName,
                MaterialColor(Record.Stops[Index].Color),
                TEXT("Tiger Fill")) != nullptr;
        }
    }
    if (!bParametersValid)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Could not create rounded-card parameters for layer: %s"),
            *Layer.Id));
        return nullptr;
    }

    Custom->Description =
        TEXT("Tiger Rounded Card SDF / validated Custom HLSL");
    Custom->OutputType = ECustomMaterialOutputType::CMOT_Float4;
    Custom->ContainsClipInstruction =
        ECustomMaterialClipInstruction::CMCI_No;
    Custom->Code = RoundedCardCustomHlsl(Record);
    Custom->RebuildOutputs();

    ColorMask->R = true;
    ColorMask->G = true;
    ColorMask->B = true;
    ColorMask->A = false;
    AlphaMask->R = false;
    AlphaMask->G = false;
    AlphaMask->B = false;
    AlphaMask->A = true;
    const bool bConnected =
        UMaterialEditingLibrary::ConnectMaterialExpressions(
            Custom, TEXT(""), ColorMask, TEXT(""))
        && UMaterialEditingLibrary::ConnectMaterialExpressions(
            Custom, TEXT(""), AlphaMask, TEXT(""))
        && UMaterialEditingLibrary::ConnectMaterialProperty(
            ColorMask, TEXT(""), EMaterialProperty::MP_EmissiveColor)
        && UMaterialEditingLibrary::ConnectMaterialProperty(
            AlphaMask, TEXT(""), EMaterialProperty::MP_Opacity);
    if (!bConnected)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Could not connect rounded-card expressions for layer: %s"),
            *Layer.Id));
        return nullptr;
    }

    const TArray<FString> CompileErrors =
        UMaterialEditingLibrary::RecompileMaterial(Material);
    for (const FString& CompileError : CompileErrors)
    {
        Result.Errors.Add(FString::Printf(
            TEXT("%s:%s"),
            *Layer.Id,
            *CompileError));
    }
    if (!CompileErrors.IsEmpty())
    {
        return nullptr;
    }
    Material->MarkPackageDirty();
    if (!SaveAssetPackage(Material))
    {
        Result.Errors.Add(FString::Printf(
            TEXT("Generated rounded-card UI Material could not be saved: %s"),
            *ObjectPath));
        return nullptr;
    }
    Result.GeneratedMaterialPaths.AddUnique(ObjectPath);
    return Material;
}

void ApplyTypedLayerVisibility(
    UWidget* Widget,
    const FTigerStudioUMGLayerRecord& Layer,
    const int32 SchemaVersion)
{
    if (!Widget || SchemaVersion < 16)
    {
        return;
    }
    if (Layer.Visibility == TEXT("Visible"))
    {
        Widget->SetVisibility(ESlateVisibility::Visible);
    }
    else if (Layer.Visibility == TEXT("HitTestInvisible"))
    {
        Widget->SetVisibility(ESlateVisibility::HitTestInvisible);
    }
}

FString SlateVisibilityAuditName(const ESlateVisibility Visibility)
{
    switch (Visibility)
    {
    case ESlateVisibility::Visible:
        return TEXT("Visible");
    case ESlateVisibility::Collapsed:
        return TEXT("Collapsed");
    case ESlateVisibility::Hidden:
        return TEXT("Hidden");
    case ESlateVisibility::HitTestInvisible:
        return TEXT("HitTestInvisible");
    case ESlateVisibility::SelfHitTestInvisible:
        return TEXT("SelfHitTestInvisible");
    default:
        return TEXT("Unknown");
    }
}

void ConfigureWidget(
    UWidget* Widget,
    const FTigerStudioUMGLayerRecord& Layer,
    UPanelWidget* Parent,
    const int32 SchemaVersion,
    const int32 CanvasZOrder,
    const FString& ParentSpacingStrategy,
    const FString& ParentSpacerSizeRule,
    const double ParentSpacerFillCoefficient,
    TMap<FString, FString>& GeneratedWidgetClasses)
{
    Widget->SetRenderOpacity(static_cast<float>(Layer.Opacity));
    Widget->SetRenderTransformPivot(
        SchemaVersion >= 5
            ? Layer.RenderTransformPivot
            : Layer.Anchor);
    Widget->SetRenderTransform(
        FWidgetTransform(
            FVector2D::ZeroVector,
            Layer.Scale,
            FVector2D::ZeroVector,
            static_cast<float>(Layer.RotationDegrees)));
    if (UCanvasPanel* Canvas = Cast<UCanvasPanel>(Parent))
    {
        UCanvasPanelSlot* Slot = Canvas->AddChildToCanvas(Widget);
        if (!Slot)
        {
            return;
        }
        // Canvas paint order is independent of insertion order. Generation
        // creates groups before leaves, so use the stable document order for
        // every root or nested CanvasPanel slot.
        Slot->SetZOrder(CanvasZOrder);
        if (SchemaVersion >= 5)
        {
            Slot->SetAnchors(FAnchors(
                Layer.CanvasSlot.AnchorMinimum.X,
                Layer.CanvasSlot.AnchorMinimum.Y,
                Layer.CanvasSlot.AnchorMaximum.X,
                Layer.CanvasSlot.AnchorMaximum.Y));
            Slot->SetOffsets(Layer.CanvasSlot.Offsets);
            Slot->SetAlignment(Layer.CanvasSlot.Alignment);
        }
        else
        {
            Slot->SetPosition(Layer.Position);
            Slot->SetSize(Layer.Size);
            Slot->SetAlignment(Layer.Anchor);
        }
        Slot->SetAutoSize(false);
        return;
    }

    UWidget* HostWidget = Widget;
    if (UWidgetTree* Tree = Widget->GetTypedOuter<UWidgetTree>())
    {
        USizeBox* SizeBox = Tree->ConstructWidget<USizeBox>(
            USizeBox::StaticClass(),
            FName(*(Layer.Id + TEXT("_TigerSlot"))));
        SizeBox->SetWidthOverride(static_cast<float>(Layer.Size.X));
        SizeBox->SetHeightOverride(static_cast<float>(Layer.Size.Y));
        SizeBox->AddChild(Widget);
        HostWidget = SizeBox;
    }

    const auto HorizontalAlignment = [&Layer]()
    {
        const FString Value = Layer.FlowSlot.HorizontalAlignment.ToLower();
        if (Value == TEXT("left")) return HAlign_Left;
        if (Value == TEXT("center")) return HAlign_Center;
        if (Value == TEXT("right")) return HAlign_Right;
        return HAlign_Fill;
    }();
    const auto VerticalAlignment = [&Layer]()
    {
        const FString Value = Layer.FlowSlot.VerticalAlignment.ToLower();
        if (Value == TEXT("top")) return VAlign_Top;
        if (Value == TEXT("center")) return VAlign_Center;
        if (Value == TEXT("bottom")) return VAlign_Bottom;
        return VAlign_Fill;
    }();
    FSlateChildSize SlotSize;
    SlotSize.SizeRule = Layer.FlowSlot.SizeRule.Equals(
        TEXT("Fill"),
        ESearchCase::IgnoreCase)
        ? ESlateSizeRule::Fill
        : ESlateSizeRule::Automatic;
    SlotSize.Value = FMath::Max(
        0.0001f,
        static_cast<float>(Layer.FlowSlot.FillCoefficient));
    const bool bUseNativeSpacers = SchemaVersion >= 17
        && ParentSpacingStrategy.Equals(
            TEXT("Spacer"),
            ESearchCase::IgnoreCase);
    FSlateChildSize SpacerSlotSize;
    SpacerSlotSize.SizeRule = ParentSpacerSizeRule.Equals(
        TEXT("Fill"),
        ESearchCase::IgnoreCase)
        ? ESlateSizeRule::Fill
        : ESlateSizeRule::Automatic;
    SpacerSlotSize.Value = FMath::Max(
        0.0001f,
        static_cast<float>(ParentSpacerFillCoefficient));
    UWidgetTree* WidgetTree = Widget->GetTypedOuter<UWidgetTree>();

    if (UHorizontalBox* Horizontal = Cast<UHorizontalBox>(Parent))
    {
        const auto AddHorizontalSpacer = [
            Horizontal,
            WidgetTree,
            &Layer,
            &SpacerSlotSize,
            &GeneratedWidgetClasses](
                const TCHAR* WidgetSuffix,
                const TCHAR* AuditSuffix,
                const float Width)
        {
            if (!WidgetTree || Width <= 0.0f)
            {
                return;
            }
            USpacer* Spacer = WidgetTree->ConstructWidget<USpacer>(
                USpacer::StaticClass(),
                FName(*(Layer.Id + WidgetSuffix)));
            Spacer->SetSize(FVector2D(
                SpacerSlotSize.SizeRule == ESlateSizeRule::Fill
                    ? 0.0f
                    : Width,
                1.0f));
            if (UHorizontalBoxSlot* SpacerSlot =
                    Horizontal->AddChildToHorizontalBox(Spacer))
            {
                SpacerSlot->SetSize(SpacerSlotSize);
                GeneratedWidgetClasses.Add(
                    Layer.Id + AuditSuffix,
                    Spacer->GetClass()->GetName());
            }
        };
        if (bUseNativeSpacers)
        {
            AddHorizontalSpacer(
                TEXT("_TigerSpacerBefore"),
                TEXT("#spacer_before"),
                static_cast<float>(Layer.FlowSlot.Padding.Left));
        }
        if (UHorizontalBoxSlot* Slot =
                Horizontal->AddChildToHorizontalBox(HostWidget))
        {
            Slot->SetPadding(
                bUseNativeSpacers
                    ? FMargin(
                        0.0,
                        Layer.FlowSlot.Padding.Top,
                        0.0,
                        Layer.FlowSlot.Padding.Bottom)
                    : Layer.FlowSlot.Padding);
            Slot->SetHorizontalAlignment(HorizontalAlignment);
            Slot->SetVerticalAlignment(VerticalAlignment);
            Slot->SetSize(SlotSize);
        }
        if (bUseNativeSpacers)
        {
            AddHorizontalSpacer(
                TEXT("_TigerSpacerAfter"),
                TEXT("#spacer_after"),
                static_cast<float>(Layer.FlowSlot.Padding.Right));
        }
    }
    else if (UVerticalBox* Vertical = Cast<UVerticalBox>(Parent))
    {
        const auto AddVerticalSpacer = [
            Vertical,
            WidgetTree,
            &Layer,
            &SpacerSlotSize,
            &GeneratedWidgetClasses](
                const TCHAR* WidgetSuffix,
                const TCHAR* AuditSuffix,
                const float Height)
        {
            if (!WidgetTree || Height <= 0.0f)
            {
                return;
            }
            USpacer* Spacer = WidgetTree->ConstructWidget<USpacer>(
                USpacer::StaticClass(),
                FName(*(Layer.Id + WidgetSuffix)));
            Spacer->SetSize(FVector2D(
                1.0f,
                SpacerSlotSize.SizeRule == ESlateSizeRule::Fill
                    ? 0.0f
                    : Height));
            if (UVerticalBoxSlot* SpacerSlot =
                    Vertical->AddChildToVerticalBox(Spacer))
            {
                SpacerSlot->SetSize(SpacerSlotSize);
                GeneratedWidgetClasses.Add(
                    Layer.Id + AuditSuffix,
                    Spacer->GetClass()->GetName());
            }
        };
        if (bUseNativeSpacers)
        {
            AddVerticalSpacer(
                TEXT("_TigerSpacerBefore"),
                TEXT("#spacer_before"),
                static_cast<float>(Layer.FlowSlot.Padding.Top));
        }
        if (UVerticalBoxSlot* Slot =
                Vertical->AddChildToVerticalBox(HostWidget))
        {
            Slot->SetPadding(
                bUseNativeSpacers
                    ? FMargin(
                        Layer.FlowSlot.Padding.Left,
                        0.0,
                        Layer.FlowSlot.Padding.Right,
                        0.0)
                    : Layer.FlowSlot.Padding);
            Slot->SetHorizontalAlignment(HorizontalAlignment);
            Slot->SetVerticalAlignment(VerticalAlignment);
            Slot->SetSize(SlotSize);
        }
        if (bUseNativeSpacers)
        {
            AddVerticalSpacer(
                TEXT("_TigerSpacerAfter"),
                TEXT("#spacer_after"),
                static_cast<float>(Layer.FlowSlot.Padding.Bottom));
        }
    }
    else if (UGridPanel* Grid = Cast<UGridPanel>(Parent))
    {
        for (int32 ColumnIndex = Layer.FlowSlot.Column;
             ColumnIndex < Layer.FlowSlot.Column + Layer.FlowSlot.ColumnSpan;
             ++ColumnIndex)
        {
            Grid->SetColumnFill(ColumnIndex, 1.0f);
        }
        for (int32 RowIndex = Layer.FlowSlot.Row;
             RowIndex < Layer.FlowSlot.Row + Layer.FlowSlot.RowSpan;
             ++RowIndex)
        {
            Grid->SetRowFill(RowIndex, 1.0f);
        }
        if (USizeBox* SlotSizeBox = Cast<USizeBox>(HostWidget))
        {
            if (HorizontalAlignment == HAlign_Fill)
            {
                SlotSizeBox->ClearWidthOverride();
            }
            if (VerticalAlignment == VAlign_Fill)
            {
                SlotSizeBox->ClearHeightOverride();
            }
        }
        if (UGridSlot* Slot = Grid->AddChildToGrid(
                HostWidget,
                Layer.FlowSlot.Row,
                Layer.FlowSlot.Column))
        {
            Slot->SetRowSpan(FMath::Max(1, Layer.FlowSlot.RowSpan));
            Slot->SetColumnSpan(FMath::Max(1, Layer.FlowSlot.ColumnSpan));
            Slot->SetPadding(Layer.FlowSlot.Padding);
            Slot->SetHorizontalAlignment(HorizontalAlignment);
            Slot->SetVerticalAlignment(VerticalAlignment);
        }
    }
    else if (UOverlay* Overlay = Cast<UOverlay>(Parent))
    {
        if (USizeBox* SlotSizeBox = Cast<USizeBox>(HostWidget))
        {
            if (HorizontalAlignment == HAlign_Fill)
            {
                SlotSizeBox->ClearWidthOverride();
            }
            if (VerticalAlignment == VAlign_Fill)
            {
                SlotSizeBox->ClearHeightOverride();
            }
        }
        if (UOverlaySlot* Slot = Overlay->AddChildToOverlay(HostWidget))
        {
            Slot->SetPadding(Layer.FlowSlot.Padding);
            Slot->SetHorizontalAlignment(HorizontalAlignment);
            Slot->SetVerticalAlignment(VerticalAlignment);
        }
    }
}

struct FTigerComponentInstanceData
{
    FString Id;
    FString ComponentId;
    TSharedPtr<FJsonObject> PropertyValues;
    FString PropertyValuesJson = TEXT("{}");
    FString ResolvedOverridesJson = TEXT("{}");
    TMap<FString, TArray<FString>> SlotRootLayerIds;
};

FString SerializeJsonObject(const TSharedPtr<FJsonObject>& Object)
{
    if (!Object)
    {
        return TEXT("{}");
    }
    FString Result;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Result);
    return FJsonSerializer::Serialize(Object.ToSharedRef(), Writer)
        ? Result
        : FString(TEXT("{}"));
}

bool ParseComponentInstancePayload(
    const FTigerStudioUMGLayerRecord& Layer,
    FTigerComponentInstanceData& OutData)
{
    const TSharedPtr<FJsonObject> Payload = ParsePayload(Layer.PayloadJson);
    const TSharedPtr<FJsonObject>* Instance = nullptr;
    if (!Payload || !Payload->TryGetObjectField(TEXT("component_instance"), Instance)
        || !Instance || !Instance->IsValid())
    {
        return false;
    }

    (*Instance)->TryGetStringField(TEXT("id"), OutData.Id);
    (*Instance)->TryGetStringField(TEXT("component_id"), OutData.ComponentId);
    const TSharedPtr<FJsonObject>* PropertyValues = nullptr;
    if ((*Instance)->TryGetObjectField(TEXT("property_values"), PropertyValues)
        && PropertyValues && PropertyValues->IsValid())
    {
        OutData.PropertyValues = *PropertyValues;
        OutData.PropertyValuesJson = SerializeJsonObject(*PropertyValues);
    }
    const TSharedPtr<FJsonObject>* ResolvedOverrides = nullptr;
    if ((*Instance)->TryGetObjectField(
            TEXT("resolved_overrides"),
            ResolvedOverrides)
        && ResolvedOverrides && ResolvedOverrides->IsValid())
    {
        OutData.ResolvedOverridesJson = SerializeJsonObject(*ResolvedOverrides);
    }
    const TArray<TSharedPtr<FJsonValue>>* SlotContents = nullptr;
    if ((*Instance)->TryGetArrayField(TEXT("slot_contents"), SlotContents)
        && SlotContents)
    {
        for (const TSharedPtr<FJsonValue>& SlotValue : *SlotContents)
        {
            const TSharedPtr<FJsonObject> Slot = SlotValue
                ? SlotValue->AsObject()
                : nullptr;
            if (!Slot)
            {
                continue;
            }
            FString SlotName;
            Slot->TryGetStringField(TEXT("slot_name"), SlotName)
                || Slot->TryGetStringField(TEXT("SlotName"), SlotName);
            const TArray<TSharedPtr<FJsonValue>>* RootIds = nullptr;
            if (SlotName.IsEmpty()
                || (!Slot->TryGetArrayField(
                        TEXT("root_layer_ids"),
                        RootIds)
                    && !Slot->TryGetArrayField(
                        TEXT("RootLayerIds"),
                        RootIds))
                || !RootIds)
            {
                continue;
            }
            TArray<FString>& Roots = OutData.SlotRootLayerIds.FindOrAdd(SlotName);
            for (const TSharedPtr<FJsonValue>& RootValue : *RootIds)
            {
                FString RootId;
                if (RootValue && RootValue->TryGetString(RootId) && !RootId.IsEmpty())
                {
                    Roots.AddUnique(RootId);
                }
            }
        }
    }
    return true;
}

FTigerStudioUMGComponentInstanceRecord MakeComponentInstanceRecord(
    const FTigerStudioUMGLayerRecord& Layer,
    const FTigerComponentInstanceData& InstanceData)
{
    FTigerStudioUMGComponentInstanceRecord Result;
    Result.Id = InstanceData.Id.IsEmpty() ? Layer.Id : InstanceData.Id;
    Result.ComponentId = InstanceData.ComponentId;
    Result.LayerId = Layer.Id;
    Result.ParentId = Layer.ParentId;
    Result.PropertyValuesJson = InstanceData.PropertyValuesJson;
    Result.ResolvedOverridesJson = InstanceData.ResolvedOverridesJson;

    TArray<FString> SlotNames;
    InstanceData.SlotRootLayerIds.GetKeys(SlotNames);
    SlotNames.Sort();
    for (const FString& SlotName : SlotNames)
    {
        FTigerStudioUMGComponentSlotContentRecord SlotContent;
        SlotContent.SlotName = SlotName;
        SlotContent.RootLayerIds =
            InstanceData.SlotRootLayerIds.FindChecked(SlotName);
        Result.SlotContents.Add(MoveTemp(SlotContent));
    }
    return Result;
}

TSharedPtr<FJsonObject> ParseCanonicalObject(const FString& Json)
{
    TSharedPtr<FJsonObject> Object;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    return FJsonSerializer::Deserialize(Reader, Object) && Object
        ? Object
        : nullptr;
}

bool ParseComponentPropertyDefault(
    const FTigerStudioUMGComponentPropertyRecord& Property,
    FString& OutDefault)
{
    TSharedPtr<FJsonObject> Wrapper;
    const FString Text = FString::Printf(
        TEXT("{\"Value\":%s}"),
        Property.DefaultValueJson.IsEmpty()
            ? TEXT("null")
            : *Property.DefaultValueJson);
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    if (!FJsonSerializer::Deserialize(Reader, Wrapper) || !Wrapper)
    {
        return false;
    }
    const TSharedPtr<FJsonValue> Value = Wrapper->TryGetField(TEXT("Value"));
    if (!Value.IsValid())
    {
        return false;
    }
    const FString Type = Property.Type.ToLower();
    if (Type == TEXT("text") || Type == TEXT("enum"))
    {
        return Value->TryGetString(OutDefault);
    }
    if (Type == TEXT("boolean"))
    {
        bool bValue = false;
        if (!Value->TryGetBool(bValue))
        {
            return false;
        }
        OutDefault = bValue ? TEXT("true") : TEXT("false");
        return true;
    }
    return false;
}

bool ConfigureComponentVariables(
    UWidgetBlueprint* Blueprint,
    const FTigerStudioUMGComponentRecord& Component,
    TArray<FString>& Errors)
{
    if (!Blueprint)
    {
        return false;
    }
    TMap<FName, FString> VariableOwners;
    for (const FTigerStudioUMGComponentPropertyRecord& Property
         : Component.Properties)
    {
        const FString Type = Property.Type.ToLower();
        if (Type == TEXT("slot"))
        {
            continue;
        }
        if (Type != TEXT("text")
            && Type != TEXT("boolean")
            && Type != TEXT("enum"))
        {
            Errors.Add(FString::Printf(
                TEXT("%s:component_property_type_runtime_unsupported:%s:%s"),
                *Component.Id,
                *Property.Name,
                *Type));
            continue;
        }

        const FName VariableName = SafeComponentVariableName(Property.Name);
        if (const FString* ExistingOwner = VariableOwners.Find(VariableName))
        {
            Errors.Add(FString::Printf(
                TEXT("%s:component_property_name_collision:%s:%s"),
                *Component.Id,
                **ExistingOwner,
                *Property.Name));
            continue;
        }
        VariableOwners.Add(VariableName, Property.Name);

        for (const FTigerStudioUMGComponentPropertyBindingRecord& Binding
             : Property.Bindings)
        {
            const bool bSupportedBinding =
                (Type == TEXT("text")
                    && Binding.TargetPath.Equals(
                        TEXT("content.text"),
                        ESearchCase::IgnoreCase))
                || (Type == TEXT("boolean")
                    && Binding.TargetPath.Equals(
                        TEXT("visible"),
                        ESearchCase::IgnoreCase));
            if (!bSupportedBinding)
            {
                Errors.Add(FString::Printf(
                    TEXT("%s:component_property_binding_runtime_unsupported:%s:%s"),
                    *Component.Id,
                    *Property.Name,
                    *Binding.TargetPath));
            }
        }

        FString DefaultValue;
        if (!ParseComponentPropertyDefault(Property, DefaultValue))
        {
            Errors.Add(FString::Printf(
                TEXT("%s:component_property_default_invalid:%s"),
                *Component.Id,
                *Property.Name));
            continue;
        }

        if (FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, VariableName)
            != INDEX_NONE)
        {
            FBlueprintEditorUtils::RemoveMemberVariable(Blueprint, VariableName);
        }
        FEdGraphPinType PinType;
        PinType.PinCategory = Type == TEXT("text")
            ? UEdGraphSchema_K2::PC_Text
            : Type == TEXT("boolean")
            ? UEdGraphSchema_K2::PC_Boolean
            : UEdGraphSchema_K2::PC_Name;
        if (!FBlueprintEditorUtils::AddMemberVariable(
                Blueprint,
                VariableName,
                PinType,
                DefaultValue))
        {
            Errors.Add(FString::Printf(
                TEXT("%s:component_property_variable_create_failed:%s"),
                *Component.Id,
                *Property.Name));
            continue;
        }
        FBlueprintEditorUtils::SetBlueprintOnlyEditableFlag(
            Blueprint,
            VariableName,
            false);
        FBlueprintEditorUtils::SetBlueprintVariableMetaData(
            Blueprint,
            VariableName,
            nullptr,
            FBlueprintMetadata::MD_ExposeOnSpawn,
            TEXT("true"));
        FBlueprintEditorUtils::SetBlueprintVariableMetaData(
            Blueprint,
            VariableName,
            nullptr,
            TEXT("TigerGeneratedComponentProperty"),
            TEXT("true"));
        if (!Property.Description.IsEmpty())
        {
            FBlueprintEditorUtils::SetBlueprintVariableMetaData(
                Blueprint,
                VariableName,
                nullptr,
                FBlueprintMetadata::MD_Tooltip,
                Property.Description);
        }
        FBlueprintEditorUtils::SetBlueprintVariableCategory(
            Blueprint,
            VariableName,
            nullptr,
            FText::FromString(TEXT("Tiger Studio|Component")));
    }
    return Errors.IsEmpty();
}

bool ApplyComponentPropertyValues(
    UUserWidget* Widget,
    const FTigerStudioUMGComponentRecord& Component,
    const TSharedPtr<FJsonObject>& Values,
    TArray<FString>& Errors,
    const FString& InstanceId)
{
    if (!Widget || !Values)
    {
        return true;
    }
    TMap<FString, const FTigerStudioUMGComponentPropertyRecord*> Definitions;
    for (const FTigerStudioUMGComponentPropertyRecord& Property
         : Component.Properties)
    {
        Definitions.Add(Property.Name, &Property);
    }
    const TSharedPtr<FJsonObject> StaticVariants =
        ParseCanonicalObject(Component.VariantValuesJson);
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Values->Values)
    {
        const FTigerStudioUMGComponentPropertyRecord* const* DefinitionPtr =
            Definitions.Find(Pair.Key);
        if (!DefinitionPtr || !*DefinitionPtr)
        {
            const TSharedPtr<FJsonValue> StaticVariant = StaticVariants
                ? StaticVariants->TryGetField(Pair.Key)
                : nullptr;
            if (!StaticVariant.IsValid())
            {
                Errors.Add(FString::Printf(
                    TEXT("%s:component_instance_property_unknown:%s"),
                    *InstanceId,
                    *Pair.Key));
            }
            else if (!Pair.Value.IsValid()
                || !FJsonValue::CompareEqual(*StaticVariant, *Pair.Value))
            {
                Errors.Add(FString::Printf(
                    TEXT("%s:component_instance_variant_mismatch:%s"),
                    *InstanceId,
                    *Pair.Key));
            }
            continue;
        }
        const FTigerStudioUMGComponentPropertyRecord& Definition = **DefinitionPtr;
        if (Definition.Type.Equals(TEXT("slot"), ESearchCase::IgnoreCase))
        {
            // Slot values are represented structurally by SlotContents.
            continue;
        }
        const FName VariableName = SafeComponentVariableName(Definition.Name);
        FProperty* Variable = Widget->GetClass()->FindPropertyByName(VariableName);
        if (!Variable)
        {
            Errors.Add(FString::Printf(
                TEXT("%s:component_instance_property_missing:%s"),
                *InstanceId,
                *Definition.Name));
            continue;
        }
        const FString Type = Definition.Type.ToLower();
        if (Type == TEXT("text"))
        {
            FString Value;
            FTextProperty* TextProperty = CastField<FTextProperty>(Variable);
            if (!TextProperty || !Pair.Value->TryGetString(Value))
            {
                Errors.Add(FString::Printf(
                    TEXT("%s:component_instance_property_type_mismatch:%s"),
                    *InstanceId,
                    *Definition.Name));
                continue;
            }
            TextProperty->SetPropertyValue_InContainer(
                Widget,
                FText::FromString(Value));
        }
        else if (Type == TEXT("boolean"))
        {
            bool bValue = false;
            FBoolProperty* BoolProperty = CastField<FBoolProperty>(Variable);
            if (!BoolProperty || !Pair.Value->TryGetBool(bValue))
            {
                Errors.Add(FString::Printf(
                    TEXT("%s:component_instance_property_type_mismatch:%s"),
                    *InstanceId,
                    *Definition.Name));
                continue;
            }
            BoolProperty->SetPropertyValue_InContainer(Widget, bValue);
        }
        else if (Type == TEXT("enum"))
        {
            FString Value;
            FNameProperty* NameProperty = CastField<FNameProperty>(Variable);
            if (!NameProperty || !Pair.Value->TryGetString(Value)
                || (!Definition.Values.IsEmpty()
                    && !Definition.Values.Contains(Value)))
            {
                Errors.Add(FString::Printf(
                    TEXT("%s:component_instance_variant_invalid:%s"),
                    *InstanceId,
                    *Definition.Name));
                continue;
            }
            NameProperty->SetPropertyValue_InContainer(Widget, FName(*Value));
        }
        else
        {
            Errors.Add(FString::Printf(
                TEXT("%s:component_instance_property_runtime_unsupported:%s:%s"),
                *InstanceId,
                *Definition.Name,
                *Type));
        }
    }
    return Errors.IsEmpty();
}

UPanelWidget* ConstructComponentPanel(
    UWidgetTree* Tree,
    const FTigerStudioUMGLayerRecord& Layer,
    const FName WidgetName)
{
    if (Layer.PanelKind == TEXT("Horizontal"))
    {
        return Tree->ConstructWidget<UHorizontalBox>(
            UHorizontalBox::StaticClass(), WidgetName);
    }
    if (Layer.PanelKind == TEXT("Vertical"))
    {
        return Tree->ConstructWidget<UVerticalBox>(
            UVerticalBox::StaticClass(), WidgetName);
    }
    if (Layer.PanelKind == TEXT("Grid"))
    {
        return Tree->ConstructWidget<UGridPanel>(
            UGridPanel::StaticClass(), WidgetName);
    }
    if (Layer.PanelKind == TEXT("Overlay"))
    {
        return Tree->ConstructWidget<UOverlay>(
            UOverlay::StaticClass(), WidgetName);
    }
    return Tree->ConstructWidget<UCanvasPanel>(
        UCanvasPanel::StaticClass(), WidgetName);
}

bool SortComponentDefinitions(
    const FTigerStudioUMGDocumentRecord& Document,
    TArray<const FTigerStudioUMGComponentRecord*>& OutOrder,
    TArray<FString>& Errors)
{
    TMap<FString, const FTigerStudioUMGComponentRecord*> ById;
    TMap<FString, FString> SafeNameOwners;
    for (const FTigerStudioUMGComponentRecord& Component : Document.Components)
    {
        if (Component.Id.IsEmpty())
        {
            Errors.Add(TEXT("component_id_missing"));
            continue;
        }
        if (ById.Contains(Component.Id))
        {
            Errors.Add(TEXT("component_id_duplicate:") + Component.Id);
            continue;
        }
        ById.Add(Component.Id, &Component);
        const FString SafeName = SafeObjectName(Component.Id);
        if (const FString* Existing = SafeNameOwners.Find(SafeName))
        {
            Errors.Add(FString::Printf(
                TEXT("component_asset_name_collision:%s:%s:%s"),
                *SafeName,
                **Existing,
                *Component.Id));
        }
        else
        {
            SafeNameOwners.Add(SafeName, Component.Id);
        }
    }

    TMap<FString, uint8> States;
    TArray<FString> Stack;
    TFunction<void(const FString&)> Visit = [&](const FString& ComponentId)
    {
        const uint8 State = States.FindRef(ComponentId);
        if (State == 2)
        {
            return;
        }
        if (State == 1)
        {
            const int32 Start = Stack.Find(ComponentId);
            TArray<FString> Cycle;
            const int32 FirstCycleIndex = Start == INDEX_NONE ? 0 : Start;
            for (int32 Index = FirstCycleIndex; Index < Stack.Num(); ++Index)
            {
                Cycle.Add(Stack[Index]);
            }
            Cycle.Add(ComponentId);
            Errors.Add(TEXT("component_dependency_cycle:")
                + FString::Join(Cycle, TEXT("->")));
            return;
        }
        const FTigerStudioUMGComponentRecord* const* ComponentPtr =
            ById.Find(ComponentId);
        if (!ComponentPtr || !*ComponentPtr)
        {
            return;
        }
        States.Add(ComponentId, 1);
        Stack.Add(ComponentId);
        for (const FString& Dependency : (*ComponentPtr)->DependencyComponentIds)
        {
            if (!ById.Contains(Dependency))
            {
                Errors.Add(FString::Printf(
                    TEXT("component_dependency_missing:%s:%s"),
                    *ComponentId,
                    *Dependency));
                continue;
            }
            Visit(Dependency);
        }
        Stack.Pop();
        States.Add(ComponentId, 2);
        OutOrder.Add(*ComponentPtr);
    };
    for (const FTigerStudioUMGComponentRecord& Component : Document.Components)
    {
        Visit(Component.Id);
    }
    return Errors.IsEmpty();
}

UWidgetBlueprint* LoadOrCreateComponentBlueprint(
    IAssetTools& AssetTools,
    const FString& WidgetPath,
    const FString& WidgetName)
{
    const FString ObjectPath = FString::Printf(
        TEXT("%s/%s.%s"), *WidgetPath, *WidgetName, *WidgetName);
    if (UWidgetBlueprint* Existing =
            LoadObject<UWidgetBlueprint>(nullptr, *ObjectPath))
    {
        return Existing;
    }
    UWidgetBlueprintFactory* Factory = NewObject<UWidgetBlueprintFactory>();
    Factory->ParentClass = UTigerStudioComponentWidget::StaticClass();
    return Cast<UWidgetBlueprint>(AssetTools.CreateAsset(
        WidgetName,
        WidgetPath,
        UWidgetBlueprint::StaticClass(),
        Factory));
}

UWidget* ConstructComponentLeaf(
    UWidgetBlueprint* Blueprint,
    const FTigerStudioUMGLayerRecord& Layer,
    const TMap<FString, FSoftObjectPath>& ResourcePaths,
    IAssetTools& AssetTools,
    const FString& GeneratedRoot,
    FTigerStudioUMGGenerationResult& Result)
{
    const TSharedPtr<FJsonObject> Payload = ParsePayload(Layer.PayloadJson);
    if (Layer.Kind == ETigerStudioUMGLayerKind::Text)
    {
        UTextBlock* Text = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(
            UTextBlock::StaticClass(), FName(*Layer.Id));
        Text->SetText(FText::FromString(
            Payload ? Payload->GetStringField(TEXT("text")) : Layer.Name));
        Text->SetColorAndOpacity(PayloadColor(
            Payload, TEXT("fill"), FLinearColor::White));
        double FontSize = 48.0;
        double FontWeight = 400.0;
        if (Payload)
        {
            Payload->TryGetNumberField(TEXT("font_size"), FontSize);
            Payload->TryGetNumberField(TEXT("font_weight"), FontWeight);
        }
        FSlateFontInfo Font = Text->GetFont();
        Font.Size = PayloadFontSizeInSlatePoints(Payload, FontSize);
        Font.TypefaceFontName = ButtonTypefaceForWeight(
            FMath::RoundToInt(FontWeight));
        Text->SetFont(Font);
        bool bAutoWrap = false;
        if (Payload)
        {
            Payload->TryGetBoolField(TEXT("auto_wrap"), bAutoWrap);
        }
        Text->SetAutoWrapText(bAutoWrap);
        if (bAutoWrap)
        {
            Text->SetClipping(EWidgetClipping::ClipToBounds);
        }
        return Text;
    }
    if (Layer.Kind == ETigerStudioUMGLayerKind::Button)
    {
        UTigerStudioButton* Button =
            Blueprint->WidgetTree->ConstructWidget<UTigerStudioButton>(
                UTigerStudioButton::StaticClass(), FName(*Layer.Id));
        Button->TigerComponentId = Layer.Id;
        UTextBlock* Label = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(
            UTextBlock::StaticClass(),
            FName(*(Layer.Id + TEXT("_Label"))));
        FString Text = Layer.Name;
        if (Payload)
        {
            Payload->TryGetStringField(TEXT("text"), Text);
        }
        Label->SetText(FText::FromString(Text));
        if (Layer.ButtonStyle.Schema == TEXT("tigerstudio.umg.button_style.v1"))
        {
            Button->SetStyle(MakeTypedButtonStyle(Layer.ButtonStyle, Layer.Size));
            Button->SetIsEnabled(Layer.ButtonStyle.Enabled);
            ApplyTypedButtonLabelStyle(
                Label,
                Layer.ButtonStyle,
                PayloadFontSizeInSlatePoints(
                    Payload,
                    Layer.ButtonStyle.Normal.FontSize));
        }
        Button->AddChild(Label);
        return Button;
    }
    if (Layer.Disposition == ETigerStudioUMGDisposition::Material)
    {
        const bool bFlipbook = !Layer.Flipbook.AssetId.IsEmpty();
        const bool bRoundedCard =
            Layer.Material.Schema == TEXT("tigerstudio.umg.ui_material.v2")
            && Layer.Material.Kind == TEXT("RoundedCard");
        UMaterial* Material = bFlipbook
            ? GenerateFlipbookMaterial(
                  AssetTools,
                  GeneratedRoot,
                  Layer,
                  LoadFlipbookTexture(Layer, ResourcePaths),
                  Result)
            : bRoundedCard
            ? GenerateRoundedCardMaterial(AssetTools, GeneratedRoot, Layer, Result)
            : GenerateGradientMaterial(AssetTools, GeneratedRoot, Layer, Result);
        if (!Material)
        {
            return nullptr;
        }
        UImage* Image = Blueprint->WidgetTree->ConstructWidget<UImage>(
            UImage::StaticClass(),
            bRoundedCard && !bFlipbook
                ? FName(*(Layer.Id + TEXT("_Visual")))
                : FName(*Layer.Id));
        Image->SetBrushFromMaterial(Material);
        Image->SetColorAndOpacity(FLinearColor::White);
        if (bRoundedCard)
        {
            UTigerStudioRoundedCardHost* MaterialHost =
                Blueprint->WidgetTree->ConstructWidget<
                    UTigerStudioRoundedCardHost>(
                    UTigerStudioRoundedCardHost::StaticClass(),
                    FName(*Layer.Id));
            MaterialHost->SetClipping(EWidgetClipping::Inherit);
            MaterialHost->TigerSizeBinding = Layer.Material.SizeBinding;
            MaterialHost->TigerFixedCardSize = Layer.Material.Size;
            MaterialHost->TigerVisualPadding = Layer.Material.VisualPadding;
            UCanvasPanelSlot* VisualSlot =
                MaterialHost->AddChildToCanvas(Image);
            const FMargin& Padding = Layer.Material.VisualPadding;
            const FVector2D SurfaceSize(
                Layer.Material.Size.X + Padding.Left + Padding.Right,
                Layer.Material.Size.Y + Padding.Top + Padding.Bottom);
            Image->SetDesiredSizeOverride(SurfaceSize);
            VisualSlot->SetAnchors(FAnchors(0.0, 0.0, 0.0, 0.0));
            VisualSlot->SetAlignment(FVector2D::ZeroVector);
            VisualSlot->SetPosition(FVector2D(
                -Padding.Left,
                -Padding.Top));
            VisualSlot->SetSize(SurfaceSize);
            VisualSlot->SetAutoSize(false);
            return MaterialHost;
        }
        return Image;
    }
    if (!Layer.ImageFill.AssetId.IsEmpty())
    {
        if (UTexture2D* Texture = LoadImageFillTexture(Layer, ResourcePaths))
        {
            return CreateImageFillWidget(
                Blueprint->WidgetTree,
                Layer,
                Texture,
                FName(*Layer.Id));
        }
        return nullptr;
    }
    UImage* Image = Blueprint->WidgetTree->ConstructWidget<UImage>(
        UImage::StaticClass(), FName(*Layer.Id));
    Image->SetColorAndOpacity(PayloadColor(
        Payload, TEXT("fill"), FLinearColor::White));
    return Image;
}

bool GenerateComponentBlueprint(
    IAssetTools& AssetTools,
    const FString& GeneratedRoot,
    const FTigerStudioUMGDocumentRecord& Document,
    const FTigerStudioUMGComponentRecord& Component,
    const TMap<FString, FSoftObjectPath>& ResourcePaths,
    const TMap<FString, UClass*>& GeneratedComponentClasses,
    UWidgetBlueprint*& OutBlueprint,
    FTigerStudioUMGGenerationResult& Result)
{
    const FString WidgetPath = GeneratedRoot / TEXT("Components");
    const FString WidgetName = TEXT("WBP_TS_C_") + SafeObjectName(Component.Id);
    OutBlueprint = LoadOrCreateComponentBlueprint(
        AssetTools, WidgetPath, WidgetName);
    if (!OutBlueprint || !OutBlueprint->WidgetTree)
    {
        Result.Errors.Add(Component.Id + TEXT(":component_widget_blueprint_create_failed"));
        return false;
    }
    OutBlueprint->Modify();
    OutBlueprint->WidgetTree->Modify();
    ConfigureComponentVariables(OutBlueprint, Component, Result.Errors);
    if (!Result.Errors.IsEmpty())
    {
        return false;
    }

    UCanvasPanel* Root = Cast<UCanvasPanel>(OutBlueprint->WidgetTree->RootWidget);
    if (!Root)
    {
        if (OutBlueprint->WidgetTree->RootWidget)
        {
            Result.Errors.Add(Component.Id + TEXT(":component_existing_root_not_canvas"));
            return false;
        }
        Root = OutBlueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
            UCanvasPanel::StaticClass(), TEXT("TigerComponentCanvas"));
        OutBlueprint->WidgetTree->RootWidget = Root;
    }
    if (UWidget* Existing =
            OutBlueprint->WidgetTree->FindWidget(TEXT("TigerComponentGeneratedRoot")))
    {
        if (UPanelWidget* Parent = Existing->GetParent())
        {
            Parent->RemoveChild(Existing);
        }
        OutBlueprint->WidgetTree->RemoveWidget(Existing);
    }
    UCanvasPanel* GeneratedPanel =
        OutBlueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
            UCanvasPanel::StaticClass(), TEXT("TigerComponentGeneratedRoot"));
    UCanvasPanelSlot* GeneratedSlot = Root->AddChildToCanvas(GeneratedPanel);
    GeneratedSlot->SetAnchors(FAnchors(0.0, 0.0, 1.0, 1.0));
    GeneratedSlot->SetOffsets(FMargin(0.0));

    TMap<FString, const FTigerStudioUMGLayerRecord*> LayersById;
    TMap<FString, int32> LayerOrders;
    for (int32 Index = 0; Index < Component.Layers.Num(); ++Index)
    {
        const FTigerStudioUMGLayerRecord& Layer = Component.Layers[Index];
        LayersById.Add(Layer.Id, &Layer);
        LayerOrders.Add(Layer.Id, Index);
    }
    TArray<FTigerStudioUMGComponentInstanceRecord> NestedComponentInstances;
    for (const FTigerStudioUMGLayerRecord& Layer : Component.Layers)
    {
        FTigerComponentInstanceData InstanceData;
        if (ParseComponentInstancePayload(Layer, InstanceData))
        {
            NestedComponentInstances.Add(
                MakeComponentInstanceRecord(Layer, InstanceData));
        }
    }
    if (!LayersById.Contains(Component.RootLayerId))
    {
        Result.Errors.Add(Component.Id + TEXT(":component_root_layer_missing:" )
            + Component.RootLayerId);
        return false;
    }
    TMap<FString, const FTigerStudioUMGComponentSlotRecord*> SlotsByLayer;
    TSet<FString> SlotNames;
    for (const FTigerStudioUMGComponentSlotRecord& Slot : Component.Slots)
    {
        const FString SafeSlotName = SafeObjectName(Slot.Name);
        if (!LayersById.Contains(Slot.LayerId))
        {
            Result.Errors.Add(Component.Id + TEXT(":component_slot_layer_missing:")
                + Slot.LayerId);
        }
        else if (SlotNames.Contains(SafeSlotName))
        {
            Result.Errors.Add(Component.Id + TEXT(":component_slot_name_collision:")
                + SafeSlotName);
        }
        SlotNames.Add(SafeSlotName);
        SlotsByLayer.Add(Slot.LayerId, &Slot);
    }
    if (!Result.Errors.IsEmpty())
    {
        return false;
    }

    TMap<FString, UPanelWidget*> ParentPanels;
    TMap<FString, UPanelWidget*> SlotRootParents;
    TMap<FString, UUserWidget*> InstanceWidgets;
    TMap<FString, FString> ComponentWidgetClasses;
    ParentPanels.Add(TEXT(""), GeneratedPanel);

    const auto ConstructNestedInstance = [&] (
        const FTigerStudioUMGLayerRecord& Layer,
        UPanelWidget* Parent,
        const FTigerComponentInstanceData& InstanceData) -> UUserWidget*
    {
        UClass* const* ComponentClass =
            GeneratedComponentClasses.Find(InstanceData.ComponentId);
        if (!ComponentClass || !*ComponentClass)
        {
            Result.Errors.Add(FString::Printf(
                TEXT("%s:component_dependency_not_generated:%s:%s"),
                *Component.Id,
                *Layer.Id,
                *InstanceData.ComponentId));
            return nullptr;
        }
        // Match the UMG Designer palette path: construct the generated class
        // as a UWidget template. ConstructWidget<UUserWidget> calls
        // CreateWidget and initializes a live foreign WidgetTree immediately;
        // instance-only NamedSlots with defaults are then unavailable for
        // template NamedSlotBindings.
        UUserWidget* Child = Cast<UUserWidget>(
            OutBlueprint->WidgetTree->ConstructWidget<UWidget>(
                *ComponentClass,
                FName(*Layer.Id)));
        if (!Child)
        {
            Result.Errors.Add(FString::Printf(
                TEXT("%s:component_dependency_template_create_failed:%s"),
                *Component.Id,
                *Layer.Id));
            return nullptr;
        }
        Child->Modify();
        const FTigerStudioUMGComponentRecord* ChildDefinition =
            Document.Components.FindByPredicate(
                [&InstanceData](const FTigerStudioUMGComponentRecord& Row)
                {
                    return Row.Id == InstanceData.ComponentId;
                });
        if (ChildDefinition)
        {
            ApplyComponentPropertyValues(
                Child,
                *ChildDefinition,
                InstanceData.PropertyValues,
                Result.Errors,
                InstanceData.Id.IsEmpty() ? Layer.Id : InstanceData.Id);
        }
        if (UTigerStudioComponentWidget* ComponentChild =
                Cast<UTigerStudioComponentWidget>(Child))
        {
            ComponentChild->TigerInstancePropertyValuesJson =
                InstanceData.PropertyValuesJson;
            ComponentChild->TigerResolvedOverridesJson =
                InstanceData.ResolvedOverridesJson;
        }
        ConfigureWidget(
            Child,
            Layer,
            Parent,
            Document.SchemaVersion,
            LayerOrders.FindRef(Layer.Id),
            TEXT("Padding"),
            TEXT("Auto"),
            1.0,
            ComponentWidgetClasses);
        ComponentWidgetClasses.Add(
            Layer.Id,
            Child->GetClass()->GetName());
        InstanceWidgets.Add(Layer.Id, Child);
        ApplyTypedLayerVisibility(Child, Layer, Document.SchemaVersion);
        Result.GeneratedWidgetVisibilityAudit.Add(
            TEXT("component:") + Component.Id + TEXT("/") + Layer.Id,
            SlateVisibilityAuditName(Child->GetVisibility()));
        for (const TPair<FString, TArray<FString>>& SlotPair
             : InstanceData.SlotRootLayerIds)
        {
            if (SlotPair.Value.IsEmpty())
            {
                // No authored override means retain the component WBP's
                // default NamedSlot content.
                continue;
            }
            UOverlay* Wrapper = OutBlueprint->WidgetTree->ConstructWidget<UOverlay>(
                UOverlay::StaticClass(),
                FName(*SafeObjectName(
                    Layer.Id + TEXT("_") + SlotPair.Key + TEXT("_SlotContent"))));
            Child->SetContentForSlot(
                FName(*SafeObjectName(SlotPair.Key)), Wrapper);
            if (Child->GetContentForSlot(
                    FName(*SafeObjectName(SlotPair.Key))) != Wrapper)
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("%s:component_instance_named_slot_missing:%s"),
                    InstanceData.Id.IsEmpty()
                        ? *Layer.Id
                        : *InstanceData.Id,
                    *SlotPair.Key));
                continue;
            }
            for (const FString& RootLayerId : SlotPair.Value)
            {
                SlotRootParents.Add(RootLayerId, Wrapper);
            }
        }
        return Child;
    };

    for (const FTigerStudioUMGLayerRecord& Layer : Component.Layers)
    {
        FTigerComponentInstanceData InstanceData;
        const bool bNestedInstance =
            ParseComponentInstancePayload(Layer, InstanceData);
        if (!bNestedInstance && Layer.Kind != ETigerStudioUMGLayerKind::Group)
        {
            continue;
        }
        UPanelWidget* Parent = SlotRootParents.FindRef(Layer.Id);
        if (!Parent)
        {
            Parent = ParentPanels.FindRef(Layer.ParentId);
        }
        Parent = Parent ? Parent : GeneratedPanel;
        if (bNestedInstance)
        {
            ConstructNestedInstance(Layer, Parent, InstanceData);
            continue;
        }
        const FTigerStudioUMGComponentSlotRecord* Slot =
            SlotsByLayer.FindRef(Layer.Id);
        UOverlay* LayerHost =
            OutBlueprint->WidgetTree->ConstructWidget<UOverlay>(
                UOverlay::StaticClass(), FName(*Layer.Id));
        ConfigureWidget(
            LayerHost,
            Layer,
            Parent,
            Document.SchemaVersion,
            LayerOrders.FindRef(Layer.Id),
            TEXT("Padding"),
            TEXT("Auto"),
            1.0,
            ComponentWidgetClasses);
        ComponentWidgetClasses.Add(
            Layer.Id,
            LayerHost->GetClass()->GetName());
        const TSharedPtr<FJsonObject> Payload = ParsePayload(Layer.PayloadJson);
        UImage* Background = OutBlueprint->WidgetTree->ConstructWidget<UImage>(
            UImage::StaticClass(),
            FName(*(Layer.Id + TEXT("_Background"))));
        Background->SetColorAndOpacity(PayloadColor(
            Payload,
            TEXT("fill"),
            FLinearColor::Transparent));
        Background->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
        AddOverlayFill(LayerHost, Background);
        ComponentWidgetClasses.Add(
            Layer.Id + TEXT("#background"),
            Background->GetClass()->GetName());
        bool bClipContent = false;
        if (Payload)
        {
            Payload->TryGetBoolField(TEXT("clip_content"), bClipContent);
        }
        LayerHost->SetClipping(
            bClipContent
                ? EWidgetClipping::ClipToBoundsAlways
                : EWidgetClipping::Inherit);
        ApplyTypedLayerVisibility(
            LayerHost,
            Layer,
            Document.SchemaVersion);
        Result.GeneratedWidgetVisibilityAudit.Add(
            TEXT("component:") + Component.Id + TEXT("/") + Layer.Id,
            SlateVisibilityAuditName(LayerHost->GetVisibility()));
        if (Slot)
        {
            UNamedSlot* NamedSlot =
                OutBlueprint->WidgetTree->ConstructWidget<UNamedSlot>(
                    UNamedSlot::StaticClass(),
                    FName(*SafeObjectName(Slot->Name)));
#if WITH_EDITORONLY_DATA
            NamedSlot->bExposeOnInstanceOnly = Slot->ExposeOnInstanceOnly;
#endif
            AddOverlayFill(LayerHost, NamedSlot);
            UOverlay* DefaultSlotContent =
                OutBlueprint->WidgetTree->ConstructWidget<UOverlay>(
                    UOverlay::StaticClass(),
                    FName(*SafeObjectName(
                        Layer.Id + TEXT("_DefaultSlotContent"))));
            NamedSlot->AddChild(DefaultSlotContent);
            ParentPanels.Add(Layer.Id, DefaultSlotContent);
            ComponentWidgetClasses.Add(
                Layer.Id + TEXT("#named_slot"),
                NamedSlot->GetClass()->GetName());
        }
        else
        {
            UPanelWidget* ContentPanel = ConstructComponentPanel(
                OutBlueprint->WidgetTree,
                Layer,
                FName(*(Layer.Id + TEXT("_Content"))));
            AddOverlayFill(LayerHost, ContentPanel);
            ParentPanels.Add(Layer.Id, ContentPanel);
            ComponentWidgetClasses.Add(
                Layer.Id + TEXT("#panel"),
                ContentPanel->GetClass()->GetName());
        }
    }
    for (const FTigerStudioUMGLayerRecord& Layer : Component.Layers)
    {
        FTigerComponentInstanceData InstanceData;
        if (ParseComponentInstancePayload(Layer, InstanceData)
            || Layer.Kind == ETigerStudioUMGLayerKind::Group)
        {
            continue;
        }
        UPanelWidget* Parent = SlotRootParents.FindRef(Layer.Id);
        if (!Parent)
        {
            Parent = ParentPanels.FindRef(Layer.ParentId);
        }
        Parent = Parent ? Parent : GeneratedPanel;
        UWidget* Widget = ConstructComponentLeaf(
            OutBlueprint,
            Layer,
            ResourcePaths,
            AssetTools,
            GeneratedRoot,
            Result);
        if (!Widget)
        {
            Result.Errors.Add(Component.Id + TEXT(":component_layer_generation_failed:")
                + Layer.Id);
            continue;
        }
        ConfigureWidget(
            Widget,
            Layer,
            Parent,
            Document.SchemaVersion,
            LayerOrders.FindRef(Layer.Id),
            TEXT("Padding"),
            TEXT("Auto"),
            1.0,
            ComponentWidgetClasses);
        ComponentWidgetClasses.Add(
            Layer.Id,
            Widget->GetClass()->GetName());
        ApplyTypedLayerVisibility(Widget, Layer, Document.SchemaVersion);
        Result.GeneratedWidgetVisibilityAudit.Add(
            TEXT("component:") + Component.Id + TEXT("/") + Layer.Id,
            SlateVisibilityAuditName(Widget->GetVisibility()));
    }
    if (!Result.Errors.IsEmpty())
    {
        return false;
    }

    FAssetRegistryModule::AssetCreated(OutBlueprint);
    OutBlueprint->MarkPackageDirty();
    FKismetEditorUtilities::CompileBlueprint(OutBlueprint);
    if (OutBlueprint->Status == BS_Error || !OutBlueprint->GeneratedClass)
    {
        Result.Errors.Add(Component.Id + TEXT(":component_widget_blueprint_compile_failed"));
        return false;
    }
    if (UTigerStudioComponentWidget* Defaults =
            Cast<UTigerStudioComponentWidget>(
                OutBlueprint->GeneratedClass->GetDefaultObject()))
    {
        Defaults->Modify();
        Defaults->TigerComponentId = Component.Id;
        Defaults->TigerBaseComponentId = Component.BaseComponentId;
        Defaults->TigerVariantValuesJson = Component.VariantValuesJson;
        Defaults->TigerComponentProperties = Component.Properties;
        Defaults->TigerComponentInstances = NestedComponentInstances;
        Defaults->TigerSourceProvider = Document.Provider;
        Defaults->TigerSourceDocumentId = Document.DocumentId;
        Defaults->TigerSourceRevision = Document.Revision;
        TSet<FString> ComponentLayerIds;
        for (const FTigerStudioUMGLayerRecord& Layer : Component.Layers)
        {
            ComponentLayerIds.Add(Layer.Id);
        }
        Defaults->TigerInteractions.Reset();
        for (const FTigerStudioUMGInteractionRecord& SourceInteraction
             : Document.Interactions)
        {
            if (!ComponentLayerIds.Contains(SourceInteraction.ComponentId))
            {
                continue;
            }
            FTigerStudioUMGInteractionRecord Interaction = SourceInteraction;
            for (FTigerStudioUMGActionRecord& Action : Interaction.Actions)
            {
                if (const FSoftObjectPath* ResourcePath =
                        ResourcePaths.Find(Action.ResourceId))
                {
                    Action.ResourcePath = *ResourcePath;
                }
            }
            Defaults->TigerInteractions.Add(MoveTemp(Interaction));
        }
#if WITH_EDITORONLY_DATA
        const FTigerStudioUMGLayerRecord* RootLayer =
            LayersById.FindRef(Component.RootLayerId);
        if (RootLayer)
        {
            Defaults->DesignTimeSize = FVector2D(
                FMath::Max(1.0, RootLayer->Size.X),
                FMath::Max(1.0, RootLayer->Size.Y));
            Defaults->DesignSizeMode = EDesignPreviewSizeMode::Custom;
        }
#endif
    }
    OutBlueprint->MarkPackageDirty();
    if (!SaveAssetPackage(OutBlueprint))
    {
        Result.Errors.Add(Component.Id + TEXT(":component_widget_blueprint_save_failed"));
        return false;
    }
    const FString AssetPath = OutBlueprint->GetPathName();
    Result.GeneratedComponentAssetPaths.Add(Component.Id, AssetPath);
    Result.GeneratedComponentClassPaths.Add(
        Component.Id,
        OutBlueprint->GeneratedClass->GetPathName());
    for (const TPair<FString, FString>& Pair : ComponentWidgetClasses)
    {
        Result.GeneratedWidgetClasses.Add(
            TEXT("component:") + Component.Id + TEXT("/") + Pair.Key,
            Pair.Value);
    }
    ++Result.GeneratedComponentCount;
    return true;
}
}

FTigerStudioUMGGenerationResult
UTigerStudioUMGImportSubsystem::GenerateDocumentFile(
    const FString& DocumentPath,
    const FString& DestinationRoot) const
{
    FTigerStudioUMGGenerationResult Result;
    const FTigerStudioUMGPreflightResult Preflight =
        PreflightDocumentFile(DocumentPath);
    if (!Preflight.bSuccess)
    {
        Result.Message = Preflight.Message;
        Result.Errors.Add(Preflight.Message);
        return Result;
    }

    FTigerStudioUMGDocumentRecord Document = Preflight.Document;
    const FString DocumentDirectory = FPaths::GetPath(DocumentPath);
    const FString SafeDocumentId = SafeObjectName(Document.DocumentId);
    const FString GeneratedRoot = FString::Printf(
        TEXT("%s/%s"),
        *DestinationRoot,
        *SafeDocumentId);

    IAssetTools& AssetTools =
        FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();
    TMap<FString, FSoftObjectPath> ResourcePaths;
    TArray<UAssetImportTask*> ImportTasks;
    TArray<FString> ImportResourceIds;
    TSet<FString> ImageFillResourceIds;
    TSet<FString> FlipbookResourceIds;
    TSet<FString> MaterializedBakedResourceIds;
    const auto CollectLayerResourceKinds = [&] (
        const FTigerStudioUMGLayerRecord& Layer)
    {
        if (!Layer.ImageFill.AssetId.IsEmpty())
        {
            ImageFillResourceIds.Add(Layer.ImageFill.AssetId);
        }
        if (!Layer.Flipbook.AssetId.IsEmpty())
        {
            FlipbookResourceIds.Add(Layer.Flipbook.AssetId);
        }
        if (Document.SchemaVersion >= 13
            && Layer.Disposition == ETigerStudioUMGDisposition::Baked
            && !Layer.ImageFill.AssetId.IsEmpty())
        {
            // Baked resources have already passed the provider-side
            // materialization and provenance gate. Keep them separate from
            // ordinary ImageFill resources so the lossless UI texture
            // contract cannot accidentally change Tile sampling behavior.
            MaterializedBakedResourceIds.Add(Layer.ImageFill.AssetId);
        }
    };
    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        CollectLayerResourceKinds(Layer);
    }
    for (const FTigerStudioUMGComponentRecord& Component : Document.Components)
    {
        for (const FTigerStudioUMGLayerRecord& Layer : Component.Layers)
        {
            CollectLayerResourceKinds(Layer);
        }
    }

    for (const FTigerStudioUMGResourceRecord& Resource : Document.Resources)
    {
        const FString SourcePath = FPaths::IsRelative(Resource.SourcePath)
            ? FPaths::ConvertRelativePathToFull(DocumentDirectory, Resource.SourcePath)
            : Resource.SourcePath;
        const FString Kind = Resource.Kind.ToLower();
        const FString Folder = Kind == TEXT("sound")
            ? TEXT("Audio")
            : Kind == TEXT("font") ? TEXT("Fonts") : TEXT("Textures");
        UAssetImportTask* Task = NewObject<UAssetImportTask>();
        Task->Filename = SourcePath;
        Task->DestinationPath = GeneratedRoot / Folder;
        Task->DestinationName = SafeObjectName(Resource.DestinationName);
        Task->bAutomated = true;
        Task->bReplaceExisting = true;
        Task->bReplaceExistingSettings = false;
        Task->bSave = true;
        ImportTasks.Add(Task);
        ImportResourceIds.Add(Resource.Id);
    }

    if (!ImportTasks.IsEmpty())
    {
        AssetTools.ImportAssetTasks(ImportTasks);
        for (int32 Index = 0; Index < ImportTasks.Num(); ++Index)
        {
            UAssetImportTask* Task = ImportTasks[Index];
            if (!Task || Task->ImportedObjectPaths.IsEmpty())
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("Failed to import resource: %s"),
                    *ImportResourceIds[Index]));
                continue;
            }
            const FString ObjectPath = Task->ImportedObjectPaths[0];
            ResourcePaths.Add(
                ImportResourceIds[Index],
                FSoftObjectPath(ObjectPath));
            Result.ImportedAssetPaths.Add(ObjectPath);
            UObject* ImportedObject = FSoftObjectPath(ObjectPath).TryLoad();
            if (UTexture2D* Texture = Cast<UTexture2D>(ImportedObject))
            {
                const FString& ResourceId = ImportResourceIds[Index];
                const bool bMaterializedBaked =
                    MaterializedBakedResourceIds.Contains(ResourceId);
                const bool bFlipbook =
                    FlipbookResourceIds.Contains(ResourceId);
                if (bMaterializedBaked)
                {
                    // Deterministic static-vector bakes are authored as
                    // straight-alpha, sRGB PNGs. UI/EditorIcon compression
                    // preserves their eight-bit RGBA contract, while disabled
                    // mip generation and clamped addressing keep the exact
                    // baked mask from bleeding or wrapping at its padding.
                    Texture->Modify();
                    Texture->LODGroup = TEXTUREGROUP_UI;
                    Texture->NeverStream = true;
                    Texture->SRGB = true;
                    Texture->CompressionNoAlpha = false;
                    Texture->CompressionSettings = TC_EditorIcon;
                    Texture->MipGenSettings = TMGS_NoMipmaps;
                    Texture->AddressX = TextureAddress::TA_Clamp;
                    Texture->AddressY = TextureAddress::TA_Clamp;
                }
                else if (bFlipbook)
                {
                    // Atlas sampling must never wrap from the last cell back
                    // into the first cell. Frame selection itself remains in
                    // the generated UV graph.
                    Texture->Modify();
                    Texture->AddressX = TextureAddress::TA_Clamp;
                    Texture->AddressY = TextureAddress::TA_Clamp;
                }
                if (bMaterializedBaked || bFlipbook)
                {
                    // PostEditChange schedules the texture rebuild after
                    // changing import settings. Finish it before saving and
                    // refresh the render resource so generation-session and
                    // reopened FWidgetRenderer proof observe the same asset.
                    Texture->PostEditChange();
                    FTextureCompilingManager::Get().FinishCompilation({ Texture });
                    Texture->UpdateResource();
                    Texture->MarkPackageDirty();
                    if (!SaveAssetPackage(Texture))
                    {
                        Result.Errors.Add(FString::Printf(
                            TEXT("Imported texture settings could not be saved: %s"),
                            *ObjectPath));
                    }
                }
            }
            else if (ImageFillResourceIds.Contains(ImportResourceIds[Index]))
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("Image Fill resource did not import as UTexture2D: %s"),
                    *ImportResourceIds[Index]));
            }
            else if (FlipbookResourceIds.Contains(ImportResourceIds[Index]))
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("Flipbook atlas resource did not import as UTexture2D: %s"),
                    *ImportResourceIds[Index]));
            }
        }
    }

    if (!Result.Errors.IsEmpty())
    {
        Result.Message = TEXT("One or more Tiger UMG resources failed to import.");
        return Result;
    }

    TArray<const FTigerStudioUMGComponentRecord*> ComponentOrder;
    if (!SortComponentDefinitions(Document, ComponentOrder, Result.Errors))
    {
        Result.Message = TEXT("Tiger UMG component dependency preflight failed.");
        return Result;
    }
    TMap<FString, UClass*> GeneratedComponentClasses;
    for (const FTigerStudioUMGComponentRecord* Component : ComponentOrder)
    {
        UWidgetBlueprint* ComponentBlueprint = nullptr;
        if (!Component
            || !GenerateComponentBlueprint(
                AssetTools,
                GeneratedRoot,
                Document,
                *Component,
                ResourcePaths,
                GeneratedComponentClasses,
                ComponentBlueprint,
                Result))
        {
            Result.Message = TEXT(
                "One or more reusable Tiger UMG components failed to generate.");
            return Result;
        }
        GeneratedComponentClasses.Add(
            Component->Id,
            ComponentBlueprint->GeneratedClass);
    }

    const FString WidgetPath = GeneratedRoot / TEXT("Widgets");
    const FString WidgetName = TEXT("WBP_TS_") + SafeDocumentId;
    const FString WidgetObjectPath = FString::Printf(
        TEXT("%s/%s.%s"),
        *WidgetPath,
        *WidgetName,
        *WidgetName);
    UWidgetBlueprint* Blueprint =
        LoadObject<UWidgetBlueprint>(nullptr, *WidgetObjectPath);
    if (!Blueprint)
    {
        UWidgetBlueprintFactory* Factory = NewObject<UWidgetBlueprintFactory>();
        Factory->ParentClass = UTigerStudioGeneratedWidget::StaticClass();
        Blueprint = Cast<UWidgetBlueprint>(
            AssetTools.CreateAsset(
                WidgetName,
                WidgetPath,
                UWidgetBlueprint::StaticClass(),
                Factory));
    }
    if (!Blueprint || !Blueprint->WidgetTree)
    {
        Result.Message = TEXT("Could not create the Tiger Widget Blueprint.");
        Result.Errors.Add(Result.Message);
        return Result;
    }

    Blueprint->Modify();
    Blueprint->WidgetTree->Modify();
    UCanvasPanel* RootCanvas = Cast<UCanvasPanel>(Blueprint->WidgetTree->RootWidget);
    if (!RootCanvas)
    {
        if (Blueprint->WidgetTree->RootWidget)
        {
            Result.Message =
                TEXT("Existing Widget Blueprint root is not a CanvasPanel.");
            Result.Errors.Add(Result.Message);
            return Result;
        }
        RootCanvas = Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
            UCanvasPanel::StaticClass(),
            TEXT("TigerCanvas"));
        Blueprint->WidgetTree->RootWidget = RootCanvas;
    }

    if (UWidget* ExistingGenerated =
            Blueprint->WidgetTree->FindWidget(TEXT("TigerGeneratedRoot")))
    {
        if (UPanelWidget* Parent = ExistingGenerated->GetParent())
        {
            Parent->RemoveChild(ExistingGenerated);
        }
        Blueprint->WidgetTree->RemoveWidget(ExistingGenerated);
    }

    UCanvasPanel* GeneratedPanel =
        Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
            UCanvasPanel::StaticClass(),
            TEXT("TigerGeneratedRoot"));
    UCanvasPanelSlot* GeneratedSlot = RootCanvas->AddChildToCanvas(GeneratedPanel);
    GeneratedSlot->SetAnchors(FAnchors(0.0, 0.0, 1.0, 1.0));
    GeneratedSlot->SetOffsets(FMargin(0.0));

    TMap<FString, UPanelWidget*> ParentPanels;
    TMap<FString, UPanelWidget*> FixedParentPanels;
    TMap<FString, UPanelWidget*> ComponentSlotRootParents;
    TMap<FString, const FTigerStudioUMGComponentRecord*> ComponentsById;
    TMap<FString, const FTigerStudioUMGComponentInstanceRecord*>
        ComponentInstancesByLayer;
    TMap<FString, FString> PanelSpacingStrategies;
    TMap<FString, FString> PanelSpacerSizeRules;
    TMap<FString, double> PanelSpacerFillCoefficients;
    TMap<FString, int32> LayerPaintOrders;
    for (const FTigerStudioUMGComponentRecord& Component : Document.Components)
    {
        ComponentsById.Add(Component.Id, &Component);
    }
    for (const FTigerStudioUMGComponentInstanceRecord& Instance
         : Document.ComponentInstances)
    {
        ComponentInstancesByLayer.Add(Instance.LayerId, &Instance);
    }
    for (int32 LayerIndex = 0;
         LayerIndex < Document.Layers.Num();
         ++LayerIndex)
    {
        LayerPaintOrders.Add(Document.Layers[LayerIndex].Id, LayerIndex);
    }
    for (const FTigerStudioUMGLayerRecord& PanelLayer : Document.Layers)
    {
        if (PanelLayer.Kind != ETigerStudioUMGLayerKind::Group)
        {
            continue;
        }
        PanelSpacingStrategies.Add(
            PanelLayer.Id,
            PanelLayer.SpacingStrategy.IsEmpty()
                ? TEXT("Padding")
                : PanelLayer.SpacingStrategy);
        PanelSpacerSizeRules.Add(
            PanelLayer.Id,
            PanelLayer.SpacerSizeRule.IsEmpty()
                ? TEXT("Auto")
                : PanelLayer.SpacerSizeRule);
        PanelSpacerFillCoefficients.Add(
            PanelLayer.Id,
            FMath::Max(0.0001, PanelLayer.SpacerFillCoefficient));
    }
    const auto ParentSpacingStrategy = [&PanelSpacingStrategies](
        const FString& ParentId)
    {
        const FString* Value = PanelSpacingStrategies.Find(ParentId);
        return Value ? *Value : FString(TEXT("Padding"));
    };
    const auto ParentSpacerSizeRule = [&PanelSpacerSizeRules](
        const FString& ParentId)
    {
        const FString* Value = PanelSpacerSizeRules.Find(ParentId);
        return Value ? *Value : FString(TEXT("Auto"));
    };
    const auto ParentSpacerFillCoefficient = [
        &PanelSpacerFillCoefficients](const FString& ParentId)
    {
        const double* Value = PanelSpacerFillCoefficients.Find(ParentId);
        return Value ? *Value : 1.0;
    };
    const auto ConstructScreenComponentInstance = [&] (
        const FTigerStudioUMGLayerRecord& Layer,
        const FTigerStudioUMGComponentInstanceRecord& Instance,
        UPanelWidget* Parent) -> UUserWidget*
    {
        UClass* const* ComponentClass =
            GeneratedComponentClasses.Find(Instance.ComponentId);
        const FTigerStudioUMGComponentRecord* const* Definition =
            ComponentsById.Find(Instance.ComponentId);
        if (!ComponentClass || !*ComponentClass || !Definition || !*Definition)
        {
            Result.Errors.Add(FString::Printf(
                TEXT("%s:screen_component_not_generated:%s"),
                *Instance.Id,
                *Instance.ComponentId));
            return nullptr;
        }
        // UMG Designer stores a child UserWidget as an uninitialized template
        // in the owner WidgetTree. This keeps instance-only NamedSlot content
        // in NamedSlotBindings until the generated screen widget initializes.
        UUserWidget* Child = Cast<UUserWidget>(
            Blueprint->WidgetTree->ConstructWidget<UWidget>(
                *ComponentClass,
                FName(*Layer.Id)));
        if (!Child)
        {
            Result.Errors.Add(
                Instance.Id + TEXT(":screen_component_template_create_failed"));
            return nullptr;
        }
        Child->Modify();
        const TSharedPtr<FJsonObject> PropertyValues =
            ParseCanonicalObject(Instance.PropertyValuesJson);
        if (!PropertyValues)
        {
            Result.Errors.Add(
                Instance.Id
                + TEXT(":component_instance_property_values_json_invalid"));
            return nullptr;
        }
        ApplyComponentPropertyValues(
            Child,
            **Definition,
            PropertyValues,
            Result.Errors,
            Instance.Id);
        if (UTigerStudioComponentWidget* ComponentChild =
                Cast<UTigerStudioComponentWidget>(Child))
        {
            ComponentChild->TigerInstancePropertyValuesJson =
                SerializeJsonObject(PropertyValues);
            ComponentChild->TigerResolvedOverridesJson =
                Instance.ResolvedOverridesJson.IsEmpty()
                    ? TEXT("{}")
                    : Instance.ResolvedOverridesJson;
        }
        ConfigureWidget(
            Child,
            Layer,
            Parent,
            Document.SchemaVersion,
            LayerPaintOrders.FindRef(Layer.Id),
            ParentSpacingStrategy(Layer.ParentId),
            ParentSpacerSizeRule(Layer.ParentId),
            ParentSpacerFillCoefficient(Layer.ParentId),
            Result.GeneratedWidgetClasses);
        ApplyTypedLayerVisibility(Child, Layer, Document.SchemaVersion);
        Result.GeneratedWidgetClasses.Add(
            Layer.Id,
            Child->GetClass()->GetName());
        Result.GeneratedWidgetVisibilityAudit.Add(
            Layer.Id,
            SlateVisibilityAuditName(Child->GetVisibility()));
        ++Result.GeneratedWidgetCount;

        for (const FTigerStudioUMGComponentSlotContentRecord& SlotContent
             : Instance.SlotContents)
        {
            if (SlotContent.RootLayerIds.IsEmpty())
            {
                // Empty roots are the explicit "use component default"
                // representation; replacing the slot would erase it.
                continue;
            }
            UOverlay* Wrapper = Blueprint->WidgetTree->ConstructWidget<UOverlay>(
                UOverlay::StaticClass(),
                FName(*SafeObjectName(
                    Layer.Id + TEXT("_") + SlotContent.SlotName
                    + TEXT("_SlotContent"))));
            const FName SlotName(*SafeObjectName(SlotContent.SlotName));
            Child->SetContentForSlot(SlotName, Wrapper);
            if (Child->GetContentForSlot(SlotName) != Wrapper)
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("%s:component_instance_named_slot_missing:%s"),
                    *Instance.Id,
                    *SlotContent.SlotName));
                continue;
            }
            for (const FString& RootLayerId : SlotContent.RootLayerIds)
            {
                if (ComponentSlotRootParents.Contains(RootLayerId))
                {
                    Result.Errors.Add(FString::Printf(
                        TEXT("%s:component_slot_root_owned_more_than_once:%s"),
                        *Instance.Id,
                        *RootLayerId));
                    continue;
                }
                ComponentSlotRootParents.Add(RootLayerId, Wrapper);
            }
        }
        return Child;
    };
    ParentPanels.Add(TEXT(""), GeneratedPanel);
    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        if (const FTigerStudioUMGComponentInstanceRecord* const* InstancePtr =
                ComponentInstancesByLayer.Find(Layer.Id))
        {
            if (Layer.Disposition != ETigerStudioUMGDisposition::Native)
            {
                Result.Errors.Add(
                    Layer.Id
                    + TEXT(":component_instance_disposition_must_be_native"));
                continue;
            }
            UPanelWidget* Parent = ComponentSlotRootParents.FindRef(Layer.Id);
            if (!Parent)
            {
                Parent = Layer.ScrollPosition == TEXT("Fixed")
                    ? FixedParentPanels.FindRef(Layer.ParentId)
                    : ParentPanels.FindRef(Layer.ParentId);
            }
            Parent = Parent ? Parent : GeneratedPanel;
            ConstructScreenComponentInstance(Layer, **InstancePtr, Parent);
            continue;
        }
        if (Layer.Disposition != ETigerStudioUMGDisposition::Native)
        {
            continue;
        }
        if (Layer.Kind == ETigerStudioUMGLayerKind::Group)
        {
            UPanelWidget* Parent = ComponentSlotRootParents.FindRef(Layer.Id);
            if (!Parent)
            {
                Parent = Layer.ScrollPosition == TEXT("Fixed")
                    ? FixedParentPanels.FindRef(Layer.ParentId)
                    : ParentPanels.FindRef(Layer.ParentId);
            }
            Parent = Parent ? Parent : GeneratedPanel;
            const bool bScrollable = Document.SchemaVersion >= 10
                && Layer.ScrollOverflow != TEXT("None");
            const bool bHasImageFill = Document.SchemaVersion >= 11
                && !Layer.ImageFill.AssetId.IsEmpty();
            UTexture2D* ImageFillTexture = bHasImageFill
                ? LoadImageFillTexture(Layer, ResourcePaths)
                : nullptr;
            if (bHasImageFill && !ImageFillTexture)
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("Image Fill texture could not be loaded: %s"),
                    *Layer.ImageFill.AssetId));
            }
            const FName ContentName = bScrollable || bHasImageFill
                ? FName(*(Layer.Id + TEXT("_Content")))
                : FName(*Layer.Id);
            UPanelWidget* ContentPanel = nullptr;
            if (Document.SchemaVersion >= 7
                && Layer.PanelKind == TEXT("Horizontal"))
            {
                ContentPanel = Blueprint->WidgetTree->ConstructWidget<UHorizontalBox>(
                    UHorizontalBox::StaticClass(),
                    ContentName);
            }
            else if (Document.SchemaVersion >= 7
                && Layer.PanelKind == TEXT("Vertical"))
            {
                ContentPanel = Blueprint->WidgetTree->ConstructWidget<UVerticalBox>(
                    UVerticalBox::StaticClass(),
                    ContentName);
            }
            else if (Document.SchemaVersion >= 9
                && Layer.PanelKind == TEXT("Grid"))
            {
                ContentPanel = Blueprint->WidgetTree->ConstructWidget<UGridPanel>(
                    UGridPanel::StaticClass(),
                    ContentName);
            }
            else if (Document.SchemaVersion >= 17
                && Layer.PanelKind == TEXT("Overlay"))
            {
                ContentPanel = Blueprint->WidgetTree->ConstructWidget<UOverlay>(
                    UOverlay::StaticClass(),
                    ContentName);
            }
            else
            {
                ContentPanel = Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
                    UCanvasPanel::StaticClass(),
                    ContentName);
            }
            UPanelWidget* AuthoredWidget = ContentPanel;
            UCanvasPanel* FixedCanvas = nullptr;
            if (bScrollable)
            {
                UOverlay* ScrollOverlay =
                    Blueprint->WidgetTree->ConstructWidget<UOverlay>(
                        UOverlay::StaticClass(),
                        FName(*Layer.Id));
                ConfigureWidget(
                    ScrollOverlay,
                    Layer,
                    Parent,
                    Document.SchemaVersion,
                    LayerPaintOrders.FindRef(Layer.Id),
                    ParentSpacingStrategy(Layer.ParentId),
                    ParentSpacerSizeRule(Layer.ParentId),
                    ParentSpacerFillCoefficient(Layer.ParentId),
                    Result.GeneratedWidgetClasses);
                AuthoredWidget = ScrollOverlay;
                const auto AddScrollChild = [](
                    UScrollBox* Scroll,
                    UWidget* Child)
                {
                    if (UScrollBoxSlot* Slot = Cast<UScrollBoxSlot>(
                            Scroll->AddChild(Child)))
                    {
                        Slot->SetHorizontalAlignment(HAlign_Fill);
                        Slot->SetVerticalAlignment(VAlign_Fill);
                        Slot->SetPadding(FMargin(0.0));
                    }
                };

                if (ImageFillTexture)
                {
                    UWidget* Background = CreateImageFillWidget(
                        Blueprint->WidgetTree,
                        Layer,
                        ImageFillTexture,
                        FName(*(Layer.Id + TEXT("_Background"))));
                    if (Background)
                    {
                        Background->SetVisibility(
                            ESlateVisibility::SelfHitTestInvisible);
                        AddOverlayFill(ScrollOverlay, Background);
                        Result.GeneratedWidgetClasses.Add(
                            Layer.Id + TEXT("#background"),
                            Background->GetClass()->GetName());
                    }
                }

                UScrollBox* PrimaryScroll =
                    Blueprint->WidgetTree->ConstructWidget<UScrollBox>(
                        UScrollBox::StaticClass(),
                        FName(*(Layer.Id + TEXT("_Scroll"))));
                PrimaryScroll->SetScrollBarVisibility(
                    ESlateVisibility::Visible);
                PrimaryScroll->SetAllowOverscroll(true);
                AddOverlayFill(ScrollOverlay, PrimaryScroll);

                if (Layer.ScrollOverflow == TEXT("Horizontal"))
                {
                    PrimaryScroll->SetOrientation(Orient_Horizontal);
                    AddScrollChild(PrimaryScroll, ContentPanel);
                }
                else if (Layer.ScrollOverflow == TEXT("Vertical"))
                {
                    PrimaryScroll->SetOrientation(Orient_Vertical);
                    AddScrollChild(PrimaryScroll, ContentPanel);
                }
                else
                {
                    PrimaryScroll->SetOrientation(Orient_Vertical);
                    UScrollBox* HorizontalScroll =
                        Blueprint->WidgetTree->ConstructWidget<UScrollBox>(
                            UScrollBox::StaticClass(),
                            FName(*(Layer.Id + TEXT("_ScrollHorizontal"))));
                    HorizontalScroll->SetOrientation(Orient_Horizontal);
                    HorizontalScroll->SetScrollBarVisibility(
                        ESlateVisibility::Visible);
                    HorizontalScroll->SetAllowOverscroll(true);
                    AddScrollChild(HorizontalScroll, ContentPanel);
                    AddScrollChild(PrimaryScroll, HorizontalScroll);
                    Result.GeneratedWidgetClasses.Add(
                        Layer.Id + TEXT("#scroll_horizontal"),
                        HorizontalScroll->GetClass()->GetName());
                }

                FixedCanvas = Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
                    UCanvasPanel::StaticClass(),
                    FName(*(Layer.Id + TEXT("_Fixed"))));
                FixedCanvas->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
                AddOverlayFill(ScrollOverlay, FixedCanvas);
                FixedParentPanels.Add(Layer.Id, FixedCanvas);
                Result.GeneratedWidgetClasses.Add(
                    Layer.Id + TEXT("#scroll"),
                    PrimaryScroll->GetClass()->GetName());
                Result.GeneratedWidgetClasses.Add(
                    Layer.Id + TEXT("#fixed"),
                    FixedCanvas->GetClass()->GetName());
            }
            else if (ImageFillTexture)
            {
                UOverlay* ImageFillOverlay =
                    Blueprint->WidgetTree->ConstructWidget<UOverlay>(
                        UOverlay::StaticClass(),
                        FName(*Layer.Id));
                ConfigureWidget(
                    ImageFillOverlay,
                    Layer,
                    Parent,
                    Document.SchemaVersion,
                    LayerPaintOrders.FindRef(Layer.Id),
                    ParentSpacingStrategy(Layer.ParentId),
                    ParentSpacerSizeRule(Layer.ParentId),
                    ParentSpacerFillCoefficient(Layer.ParentId),
                    Result.GeneratedWidgetClasses);
                UWidget* Background = CreateImageFillWidget(
                    Blueprint->WidgetTree,
                    Layer,
                    ImageFillTexture,
                    FName(*(Layer.Id + TEXT("_Background"))));
                if (Background)
                {
                    Background->SetVisibility(
                        ESlateVisibility::SelfHitTestInvisible);
                    AddOverlayFill(ImageFillOverlay, Background);
                    Result.GeneratedWidgetClasses.Add(
                        Layer.Id + TEXT("#background"),
                        Background->GetClass()->GetName());
                }
                AddOverlayFill(ImageFillOverlay, ContentPanel);
                AuthoredWidget = ImageFillOverlay;
            }
            else
            {
                ConfigureWidget(
                    ContentPanel,
                    Layer,
                    Parent,
                    Document.SchemaVersion,
                    LayerPaintOrders.FindRef(Layer.Id),
                    ParentSpacingStrategy(Layer.ParentId),
                    ParentSpacerSizeRule(Layer.ParentId),
                    ParentSpacerFillCoefficient(Layer.ParentId),
                    Result.GeneratedWidgetClasses);
            }
            const TSharedPtr<FJsonObject> Payload =
                ParsePayload(Layer.PayloadJson);
            bool bClipContent = false;
            if (Payload)
            {
                Payload->TryGetBoolField(
                    TEXT("clip_content"),
                    bClipContent);
            }
            AuthoredWidget->SetClipping(
                bClipContent
                    ? EWidgetClipping::ClipToBoundsAlways
                    : EWidgetClipping::Inherit);
            ApplyTypedLayerVisibility(
                AuthoredWidget,
                Layer,
                Document.SchemaVersion);
            ParentPanels.Add(Layer.Id, ContentPanel);
            Result.GeneratedWidgetClasses.Add(
                Layer.Id,
                AuthoredWidget->GetClass()->GetName());
            Result.GeneratedWidgetVisibilityAudit.Add(
                Layer.Id,
                SlateVisibilityAuditName(
                    AuthoredWidget->GetVisibility()));
            ++Result.GeneratedWidgetCount;
        }
    }

    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        if (ComponentInstancesByLayer.Contains(Layer.Id))
        {
            continue;
        }
        const bool bNative =
            Layer.Disposition == ETigerStudioUMGDisposition::Native;
        const bool bMaterial =
            Layer.Disposition == ETigerStudioUMGDisposition::Material;
        const bool bBaked = Document.SchemaVersion >= 13
            && Layer.Disposition == ETigerStudioUMGDisposition::Baked;
        if ((!bNative && !bMaterial && !bBaked)
            || Layer.Kind == ETigerStudioUMGLayerKind::Group)
        {
            continue;
        }
        UPanelWidget* Parent = ComponentSlotRootParents.FindRef(Layer.Id);
        if (!Parent)
        {
            Parent = Layer.ScrollPosition == TEXT("Fixed")
                ? FixedParentPanels.FindRef(Layer.ParentId)
                : ParentPanels.FindRef(Layer.ParentId);
        }
        Parent = Parent ? Parent : GeneratedPanel;
        const TSharedPtr<FJsonObject> Payload = ParsePayload(Layer.PayloadJson);
        UWidget* Widget = nullptr;
        UImage* Image = nullptr;
        UTextBlock* Text = nullptr;

        if (Layer.Kind == ETigerStudioUMGLayerKind::Text)
        {
            Text = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(
                UTextBlock::StaticClass(),
                FName(*Layer.Id));
            Text->SetText(FText::FromString(
                Payload ? Payload->GetStringField(TEXT("text")) : Layer.Name));
            Text->SetColorAndOpacity(PayloadColor(
                Payload,
                TEXT("fill"),
                FLinearColor::White));
            FSlateFontInfo Font = Text->GetFont();
            double FontSize = 48.0;
            double FontWeight = 400.0;
            if (Payload)
            {
                Payload->TryGetNumberField(TEXT("font_size"), FontSize);
                Payload->TryGetNumberField(TEXT("font_weight"), FontWeight);
            }
            Font.Size = PayloadFontSizeInSlatePoints(Payload, FontSize);
            Font.TypefaceFontName = ButtonTypefaceForWeight(
                FMath::RoundToInt(FontWeight));
            Text->SetFont(Font);
            bool bAutoWrap = false;
            if (Payload)
            {
                Payload->TryGetBoolField(TEXT("auto_wrap"), bAutoWrap);
            }
            Text->SetAutoWrapText(bAutoWrap);
            if (bAutoWrap)
            {
                // Painter clips fixed-width text to the authored rectangle.
                // Match that behavior so wrapped copy cannot paint over a
                // sibling CTA when its source box has a fixed height.
                Text->SetClipping(EWidgetClipping::ClipToBounds);
            }
            Widget = Text;
        }
        else if (Layer.Kind == ETigerStudioUMGLayerKind::Button)
        {
            UTigerStudioButton* Button =
                Blueprint->WidgetTree->ConstructWidget<UTigerStudioButton>(
                    UTigerStudioButton::StaticClass(),
                    FName(*Layer.Id));
            Button->TigerComponentId = Layer.Id;
            UTextBlock* Label =
                Blueprint->WidgetTree->ConstructWidget<UTextBlock>(
                    UTextBlock::StaticClass(),
                    FName(*(Layer.Id + TEXT("_Label"))));
            FString LabelText = Layer.Name;
            if (Payload)
            {
                Payload->TryGetStringField(TEXT("text"), LabelText);
            }
            Label->SetText(FText::FromString(LabelText));

            const bool bTypedButtonStyle = Document.SchemaVersion >= 16
                && Layer.ButtonStyle.Schema
                    == TEXT("tigerstudio.umg.button_style.v1");
            const float AppliedButtonLabelFontSize =
                PayloadFontSizeInSlatePoints(
                    Payload,
                    Layer.ButtonStyle.Normal.FontSize);
            if (bTypedButtonStyle)
            {
                Button->SetStyle(MakeTypedButtonStyle(
                    Layer.ButtonStyle,
                    Layer.Size));
                Button->SetIsEnabled(Layer.ButtonStyle.Enabled);
                ApplyTypedButtonLabelStyle(
                    Label,
                    Layer.ButtonStyle,
                    AppliedButtonLabelFontSize);
            }

            const bool bTypedImageFill = Document.SchemaVersion >= 11
                && !Layer.ImageFill.AssetId.IsEmpty();
            UTexture2D* ButtonTexture = bTypedImageFill
                ? LoadImageFillTexture(Layer, ResourcePaths)
                : nullptr;
            if (!ButtonTexture && !Layer.AssetId.IsEmpty())
            {
                if (const FSoftObjectPath* AssetPath =
                        ResourcePaths.Find(Layer.AssetId))
                {
                    ButtonTexture = Cast<UTexture2D>(AssetPath->TryLoad());
                }
            }
            if (bTypedImageFill && !ButtonTexture)
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("Image Fill texture could not be loaded: %s"),
                    *Layer.ImageFill.AssetId));
            }
            if (bTypedButtonStyle)
            {
                Result.GeneratedButtonStyleAudit.Add(
                    Layer.Id,
                    ButtonStyleAuditJson(
                        Layer.ButtonStyle,
                        bTypedImageFill && ButtonTexture,
                        PayloadFontSizeUnitForAudit(Payload),
                        AppliedButtonLabelFontSize));
            }

            if (bTypedImageFill && ButtonTexture)
            {
                // Keep typed image fills in an explicit UImage behind the
                // label.  Serializing a texture/UV region only inside a
                // UButton FButtonStyle can lose the authored crop when the
                // Widget Blueprint is compiled and reconstructed.
                FSlateBrush NoBrush;
                NoBrush.DrawAs = ESlateBrushDrawType::NoDrawType;
                FButtonStyle ButtonStyle = Button->GetStyle();
                ButtonStyle
                    .SetNormal(NoBrush)
                    .SetHovered(NoBrush)
                    .SetPressed(NoBrush)
                    .SetDisabled(NoBrush)
                    .SetNormalPadding(FMargin(0.0))
                    .SetPressedPadding(FMargin(0.0));
                Button->SetStyle(ButtonStyle);

                UOverlay* ContentOverlay =
                    Blueprint->WidgetTree->ConstructWidget<UOverlay>(
                        UOverlay::StaticClass(),
                        FName(*(Layer.Id + TEXT("_Content"))));
                UWidget* Background = CreateImageFillWidget(
                    Blueprint->WidgetTree,
                    Layer,
                    ButtonTexture,
                    FName(*(Layer.Id + TEXT("_Background"))));
                if (Background)
                {
                    Background->SetVisibility(
                        ESlateVisibility::SelfHitTestInvisible);
                    AddOverlayFill(ContentOverlay, Background);
                }
                if (UOverlaySlot* LabelSlot =
                        ContentOverlay->AddChildToOverlay(Label))
                {
                    LabelSlot->SetHorizontalAlignment(HAlign_Center);
                    LabelSlot->SetVerticalAlignment(VAlign_Center);
                    LabelSlot->SetPadding(FMargin(0.0));
                }
                if (UButtonSlot* ButtonSlot = Cast<UButtonSlot>(
                        Button->AddChild(ContentOverlay)))
                {
                    ButtonSlot->SetHorizontalAlignment(HAlign_Fill);
                    ButtonSlot->SetVerticalAlignment(VAlign_Fill);
                    ButtonSlot->SetPadding(FMargin(0.0));
                }
            }
            else if (ButtonTexture)
            {
                FSlateBrush BackgroundBrush;
                if (bTypedImageFill)
                {
                    BackgroundBrush = MakeImageFillBrush(
                        ButtonTexture,
                        Layer);
                }
                else
                {
                    BackgroundBrush.SetResourceObject(ButtonTexture);
                    BackgroundBrush.SetImageSize(FVector2D(
                        ButtonTexture->GetSizeX(),
                        ButtonTexture->GetSizeY()));
                    BackgroundBrush.DrawAs = ESlateBrushDrawType::Image;
                    BackgroundBrush.ImageType =
                        ESlateBrushImageType::FullColor;
                }
                FButtonStyle ButtonStyle = Button->GetStyle();
                ButtonStyle
                    .SetNormal(BackgroundBrush)
                    .SetHovered(BackgroundBrush)
                    .SetPressed(BackgroundBrush)
                    .SetDisabled(BackgroundBrush)
                    .SetNormalPadding(FMargin(0.0))
                    .SetPressedPadding(FMargin(0.0));
                Button->SetStyle(ButtonStyle);
                Button->AddChild(Label);
            }
            else
            {
                Button->AddChild(Label);
            }
            Widget = Button;
        }
        else
        {
            if (bMaterial)
            {
                const bool bFlipbook = Document.SchemaVersion >= 12
                    && !Layer.Flipbook.AssetId.IsEmpty();
                const bool bRoundedCard =
                    Layer.Material.Schema
                        == TEXT("tigerstudio.umg.ui_material.v2")
                    && Layer.Material.Kind == TEXT("RoundedCard");
                UE_LOG(
                    LogTemp,
                    Display,
                    TEXT("TigerStudioUMG: generating UI Material for %s"),
                    *Layer.Id);
                UMaterial* Material = bFlipbook
                    ? GenerateFlipbookMaterial(
                          AssetTools,
                          GeneratedRoot,
                          Layer,
                          LoadFlipbookTexture(Layer, ResourcePaths),
                          Result)
                    : bRoundedCard
                        ? GenerateRoundedCardMaterial(
                              AssetTools,
                              GeneratedRoot,
                              Layer,
                              Result)
                        : GenerateGradientMaterial(
                              AssetTools,
                              GeneratedRoot,
                              Layer,
                              Result);
                if (Material)
                {
                    UE_LOG(
                        LogTemp,
                        Display,
                        TEXT("TigerStudioUMG: assigning UI Material to %s"),
                        *Layer.Id);
                    // Material generation may compile shaders, save packages,
                    // and trigger GC. Construct the widget only afterwards so
                    // an unattached transient UImage cannot be collected.
                    const FName ImageName = bRoundedCard && !bFlipbook
                        ? FName(*(Layer.Id + TEXT("_Visual")))
                        : FName(*Layer.Id);
                    Image = Blueprint->WidgetTree->ConstructWidget<UImage>(
                        UImage::StaticClass(),
                        ImageName);
                    Image->SetBrushFromMaterial(Material);
                    Image->SetColorAndOpacity(FLinearColor::White);
                    if (bRoundedCard)
                    {
                        // The stable layer widget keeps the original layout
                        // geometry while its visual child grows into explicit
                        // non-clipping padding. Animations/interactions remain
                        // bound to Layer.Id instead of the expanded child.
                        UTigerStudioRoundedCardHost* MaterialHost =
                            Blueprint->WidgetTree->ConstructWidget<
                                UTigerStudioRoundedCardHost>(
                                UTigerStudioRoundedCardHost::StaticClass(),
                                FName(*Layer.Id));
                        MaterialHost->SetClipping(EWidgetClipping::Inherit);
                        MaterialHost->TigerSizeBinding =
                            Layer.Material.SizeBinding;
                        MaterialHost->TigerFixedCardSize =
                            Layer.Material.Size;
                        MaterialHost->TigerVisualPadding =
                            Layer.Material.VisualPadding;
                        UCanvasPanelSlot* VisualSlot =
                            MaterialHost->AddChildToCanvas(Image);
                        const FMargin& Padding =
                            Layer.Material.VisualPadding;
                        const FVector2D SurfaceSize(
                            Layer.Material.Size.X
                                + Padding.Left
                                + Padding.Right,
                            Layer.Material.Size.Y
                                + Padding.Top
                                + Padding.Bottom);
                        Image->SetDesiredSizeOverride(SurfaceSize);
                        VisualSlot->SetAnchors(FAnchors(0.0, 0.0, 0.0, 0.0));
                        VisualSlot->SetAlignment(FVector2D::ZeroVector);
                        VisualSlot->SetPosition(FVector2D(
                            -Padding.Left,
                            -Padding.Top));
                        VisualSlot->SetSize(SurfaceSize);
                        VisualSlot->SetAutoSize(false);
                        Widget = MaterialHost;
                    }
                    else
                    {
                        Widget = Image;
                    }
                    UE_LOG(
                        LogTemp,
                        Display,
                        TEXT("TigerStudioUMG: assigned UI Material to %s"),
                        *Layer.Id);
                }
            }
            else if (bBaked)
            {
                // Schema-13 Baked is already materialized by the provider.
                // Preflight guarantees the narrow Stretch/white typed
                // ImageFill contract, so generation imports and constructs a
                // UImage without invoking any Unreal-side rasterizer.
                if (UTexture2D* Texture = LoadImageFillTexture(
                        Layer,
                        ResourcePaths))
                {
                    Widget = CreateImageFillWidget(
                        Blueprint->WidgetTree,
                        Layer,
                        Texture,
                        FName(*Layer.Id));
                }
                else
                {
                    Result.Errors.Add(FString::Printf(
                        TEXT("Materialized Baked texture could not be loaded: %s"),
                        *Layer.ImageFill.AssetId));
                }
            }
            else
            {
                const bool bTypedImageFill = Document.SchemaVersion >= 11
                    && !Layer.ImageFill.AssetId.IsEmpty();
                if (bTypedImageFill)
                {
                    if (UTexture2D* Texture = LoadImageFillTexture(
                            Layer,
                            ResourcePaths))
                    {
                        Widget = CreateImageFillWidget(
                            Blueprint->WidgetTree,
                            Layer,
                            Texture,
                            FName(*Layer.Id));
                    }
                    else
                    {
                        Result.Errors.Add(FString::Printf(
                            TEXT("Image Fill texture could not be loaded: %s"),
                            *Layer.ImageFill.AssetId));
                    }
                }
                else
                {
                    // Legacy standalone Image layers remain direct Stretch
                    // brushes when they have only Layer.AssetId.
                    Image = Blueprint->WidgetTree->ConstructWidget<UImage>(
                        UImage::StaticClass(),
                        FName(*Layer.Id));
                    if (const FSoftObjectPath* AssetPath =
                            ResourcePaths.Find(Layer.AssetId))
                    {
                        if (UTexture2D* Texture = Cast<UTexture2D>(
                                AssetPath->TryLoad()))
                        {
                            Image->SetBrushFromTexture(Texture, true);
                        }
                    }
                    Image->SetColorAndOpacity(PayloadColor(
                        Payload,
                        TEXT("fill"),
                        FLinearColor::White));
                    Widget = Image;
                }
            }
        }

        if (Widget)
        {
            ConfigureWidget(
                Widget,
                Layer,
                Parent,
                Document.SchemaVersion,
                LayerPaintOrders.FindRef(Layer.Id),
                ParentSpacingStrategy(Layer.ParentId),
                ParentSpacerSizeRule(Layer.ParentId),
                ParentSpacerFillCoefficient(Layer.ParentId),
                Result.GeneratedWidgetClasses);
            bool bArtboardBackground = false;
            if (Layer.Kind == ETigerStudioUMGLayerKind::Image
                && Payload
                && Payload->TryGetBoolField(
                    TEXT("artboard_background"),
                    bArtboardBackground)
                && bArtboardBackground)
            {
                // The synthesized artboard paint is visual-only.  It must
                // never intercept pointer input intended for authored UMG
                // controls placed above it.
                Widget->SetVisibility(
                    ESlateVisibility::SelfHitTestInvisible);
            }
            // Typed schema-v16 visibility is authoritative and is applied
            // after the payload fallback.
            ApplyTypedLayerVisibility(
                Widget,
                Layer,
                Document.SchemaVersion);
            Result.GeneratedWidgetClasses.Add(
                Layer.Id,
                Widget->GetClass()->GetName());
            Result.GeneratedWidgetVisibilityAudit.Add(
                Layer.Id,
                SlateVisibilityAuditName(Widget->GetVisibility()));
            ++Result.GeneratedWidgetCount;
        }
    }

    UE_LOG(
        LogTemp,
        Display,
        TEXT("TigerStudioUMG: completed widget construction"));

    if (!Result.Errors.IsEmpty())
    {
        Result.Message =
            TEXT("One or more Tiger UMG widgets or materials failed to generate.");
        return Result;
    }

    Blueprint->Animations.RemoveAll(
        [](const UWidgetAnimation* Animation)
        {
            return Animation
                && Animation->GetName().StartsWith(TEXT("Tiger_"));
        });
    TMap<FString, TArray<const FTigerStudioUMGAnimationTrackRecord*>> AnimationGroups;
    for (const FTigerStudioUMGAnimationTrackRecord& Track : Document.Animations)
    {
        AnimationGroups.FindOrAdd(
            Track.AnimationName.IsEmpty() ? TEXT("TigerTimeline") : Track.AnimationName)
            .Add(&Track);
    }
    for (const TPair<FString, TArray<const FTigerStudioUMGAnimationTrackRecord*>>& Group :
         AnimationGroups)
    {
        const FString AnimationName = TEXT("Tiger_") + SafeObjectName(Group.Key);
        UWidgetAnimation* Animation = NewObject<UWidgetAnimation>(
            Blueprint,
            FName(*AnimationName),
            RF_Transactional);
        Animation->SetDisplayLabel(Group.Key);
        Animation->MovieScene = NewObject<UMovieScene>(
            Animation,
            FName(*AnimationName),
            RF_Transactional);
        Animation->MovieScene->SetDisplayRate(
            FFrameRate(FMath::Max(1, FMath::RoundToInt(Document.FrameRate)), 1));
        Animation->MovieScene->SetTickResolutionDirectly(FFrameRate(1000, 1));
        Animation->MovieScene->SetPlaybackRange(
            TRange<FFrameNumber>(
                FFrameNumber(0),
                FFrameNumber(Document.DurationMilliseconds + 1)));

        TMap<FString, TArray<const FTigerStudioUMGAnimationTrackRecord*>> LayerTracks;
        for (const FTigerStudioUMGAnimationTrackRecord* Track : Group.Value)
        {
            LayerTracks.FindOrAdd(Track->LayerId).Add(Track);
        }
        for (const TPair<FString, TArray<const FTigerStudioUMGAnimationTrackRecord*>>&
             LayerGroup : LayerTracks)
        {
            const FGuid BindingId = Animation->MovieScene->AddPossessable(
                LayerGroup.Key,
                UWidget::StaticClass());
            FWidgetAnimationBinding Binding;
            Binding.WidgetName = FName(*LayerGroup.Key);
            Binding.AnimationGuid = BindingId;
            Animation->AnimationBindings.Add(Binding);

            UMovieScene2DTransformSection* TransformSection = nullptr;
            UMovieSceneFloatSection* OpacitySection = nullptr;
            for (const FTigerStudioUMGAnimationTrackRecord* Track : LayerGroup.Value)
            {
                const FString Property = Track->Property.ToLower();
                if (Property == TEXT("opacity"))
                {
                    if (!OpacitySection)
                    {
                        UMovieSceneFloatTrack* FloatTrack =
                            Animation->MovieScene->AddTrack<UMovieSceneFloatTrack>(
                                BindingId);
                        FloatTrack->SetPropertyNameAndPath(
                            TEXT("RenderOpacity"),
                            TEXT("RenderOpacity"));
                        OpacitySection = Cast<UMovieSceneFloatSection>(
                            FloatTrack->CreateNewSection());
                        OpacitySection->SetRange(
                            Animation->MovieScene->GetPlaybackRange());
                        FloatTrack->AddSection(*OpacitySection);
                    }
                    for (const FTigerStudioUMGKeyframeRecord& Key : Track->Keyframes)
                    {
                        AddKey(
                            OpacitySection->GetChannel(),
                            Key,
                            static_cast<float>(Key.Value.X));
                    }
                    continue;
                }
                if (!TransformSection)
                {
                    UMovieScene2DTransformTrack* TransformTrack =
                        Animation->MovieScene->AddTrack<UMovieScene2DTransformTrack>(
                            BindingId);
                    TransformTrack->SetPropertyNameAndPath(
                        TEXT("RenderTransform"),
                        TEXT("RenderTransform"));
                    TransformSection = Cast<UMovieScene2DTransformSection>(
                        TransformTrack->CreateNewSection());
                    TransformSection->SetMask(
                        FMovieScene2DTransformMask(
                            EMovieScene2DTransformChannel::AllTransform));
                    TransformSection->SetRange(
                        Animation->MovieScene->GetPlaybackRange());
                    TransformTrack->AddSection(*TransformSection);
                }
                for (const FTigerStudioUMGKeyframeRecord& Key : Track->Keyframes)
                {
                    if (Property == TEXT("position"))
                    {
                        AddKey(
                            TransformSection->Translation[0],
                            Key,
                            static_cast<float>(Key.Value.X));
                        AddKey(
                            TransformSection->Translation[1],
                            Key,
                            static_cast<float>(Key.Value.Y));
                    }
                    else if (Property == TEXT("scale"))
                    {
                        AddKey(
                            TransformSection->Scale[0],
                            Key,
                            static_cast<float>(Key.Value.X));
                        AddKey(
                            TransformSection->Scale[1],
                            Key,
                            static_cast<float>(Key.Value.Y));
                    }
                    else if (Property == TEXT("rotation"))
                    {
                        AddKey(
                            TransformSection->Rotation,
                            Key,
                            static_cast<float>(Key.Value.X));
                    }
                }
            }
        }
        Blueprint->Animations.Add(Animation);
        ++Result.GeneratedAnimationCount;
    }

    for (FTigerStudioUMGInteractionRecord& Interaction : Document.Interactions)
    {
        for (FTigerStudioUMGActionRecord& Action : Interaction.Actions)
        {
            if (const FSoftObjectPath* ResourcePath =
                    ResourcePaths.Find(Action.ResourceId))
            {
                Action.ResourcePath = *ResourcePath;
            }
            if (Action.Type.Equals(TEXT("play_animation"), ESearchCase::IgnoreCase)
                && !Action.Name.StartsWith(TEXT("Tiger_")))
            {
                Action.Name = TEXT("Tiger_") + SafeObjectName(Action.Name);
            }
        }
    }

    FAssetRegistryModule::AssetCreated(Blueprint);
    Blueprint->MarkPackageDirty();
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    if (Blueprint->Status == BS_Error || !Blueprint->GeneratedClass)
    {
        Result.Message = TEXT("Generated Widget Blueprint did not compile.");
        Result.Errors.Add(Result.Message);
        return Result;
    }
    if (UTigerStudioGeneratedWidget* Defaults =
            Cast<UTigerStudioGeneratedWidget>(
                Blueprint->GeneratedClass->GetDefaultObject()))
    {
        Defaults->Modify();
#if WITH_EDITORONLY_DATA
        // UMG Designer reads these public editor-only UUserWidget properties
        // from the generated class default object.  Custom mode makes both
        // the preview area and widget size use DesignTimeSize, so a portrait
        // authoring document opens at its authored dimensions instead of the
        // editor's shared landscape screen preset.
        Defaults->DesignTimeSize = FVector2D(
            FMath::Max(1, Document.Width),
            FMath::Max(1, Document.Height));
        Defaults->DesignSizeMode = EDesignPreviewSizeMode::Custom;
#endif
        Defaults->TigerSourceProvider = Document.Provider;
        Defaults->TigerSourceDocumentId = Document.DocumentId;
        Defaults->TigerSourceRevision = Document.Revision;
        Defaults->TigerInteractions = Document.Interactions;
        Defaults->TigerComponentInstances = Document.ComponentInstances;
    }
    Blueprint->MarkPackageDirty();
    if (!SaveAssetPackage(Blueprint))
    {
        Result.Message = TEXT("Generated Widget Blueprint could not be saved.");
        Result.Errors.Add(Result.Message);
        return Result;
    }

    Result.bSuccess = true;
    Result.GeneratedAssetPath = WidgetObjectPath;
    Result.Message = FString::Printf(
        TEXT("Generated %d widgets and %d animations."),
        Result.GeneratedWidgetCount,
        Result.GeneratedAnimationCount);
    return Result;
}
