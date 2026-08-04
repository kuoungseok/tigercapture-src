#include "TigerStudioUMGImportSubsystem.h"

#include "Animation/MovieScene2DTransformSection.h"
#include "Animation/MovieScene2DTransformTrack.h"
#include "Animation/WidgetAnimation.h"
#include "AssetImportTask.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetToolsModule.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ButtonSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/GridPanel.h"
#include "Components/GridSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/PanelWidget.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/ScaleBox.h"
#include "Components/ScaleBoxSlot.h"
#include "Components/SizeBox.h"
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
#include "MaterialEditingLibrary.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpressionComponentMask.h"
#include "Materials/MaterialExpressionCustom.h"
#include "Materials/MaterialExpressionScalarParameter.h"
#include "Materials/MaterialExpressionTextureCoordinate.h"
#include "Materials/MaterialExpressionVectorParameter.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "MovieScene.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Styling/SlateBrush.h"
#include "Styling/SlateTypes.h"
#include "TigerStudioButton.h"
#include "TigerStudioGeneratedWidget.h"
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
            "? ((%sP.y < 0.0) ? CornerRadii.x : CornerRadii.w) "
            ": ((%sP.y < 0.0) ? CornerRadii.y : CornerRadii.z);\n"),
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
        "float2 CardPoint = PixelPosition - CardSize.xy * 0.5;\n");
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

void ConfigureWidget(
    UWidget* Widget,
    const FTigerStudioUMGLayerRecord& Layer,
    UPanelWidget* Parent,
    const int32 SchemaVersion)
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

    if (UHorizontalBox* Horizontal = Cast<UHorizontalBox>(Parent))
    {
        if (UHorizontalBoxSlot* Slot =
                Horizontal->AddChildToHorizontalBox(HostWidget))
        {
            Slot->SetPadding(Layer.FlowSlot.Padding);
            Slot->SetHorizontalAlignment(HorizontalAlignment);
            Slot->SetVerticalAlignment(VerticalAlignment);
            Slot->SetSize(SlotSize);
        }
    }
    else if (UVerticalBox* Vertical = Cast<UVerticalBox>(Parent))
    {
        if (UVerticalBoxSlot* Slot =
                Vertical->AddChildToVerticalBox(HostWidget))
        {
            Slot->SetPadding(Layer.FlowSlot.Padding);
            Slot->SetHorizontalAlignment(HorizontalAlignment);
            Slot->SetVerticalAlignment(VerticalAlignment);
            Slot->SetSize(SlotSize);
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
    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        if (!Layer.ImageFill.AssetId.IsEmpty())
        {
            ImageFillResourceIds.Add(Layer.ImageFill.AssetId);
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
                Texture->Modify();
                Texture->LODGroup = TEXTUREGROUP_UI;
                Texture->NeverStream = true;
                Texture->SRGB = true;
                Texture->MarkPackageDirty();
                SaveAssetPackage(Texture);
            }
            else if (ImageFillResourceIds.Contains(ImportResourceIds[Index]))
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("Image Fill resource did not import as UTexture2D: %s"),
                    *ImportResourceIds[Index]));
            }
        }
    }

    if (!Result.Errors.IsEmpty())
    {
        Result.Message = TEXT("One or more Tiger UMG resources failed to import.");
        return Result;
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
    ParentPanels.Add(TEXT(""), GeneratedPanel);
    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        if (Layer.Disposition != ETigerStudioUMGDisposition::Native)
        {
            continue;
        }
        if (Layer.Kind == ETigerStudioUMGLayerKind::Group)
        {
            UPanelWidget* Parent = Layer.ScrollPosition == TEXT("Fixed")
                ? FixedParentPanels.FindRef(Layer.ParentId)
                : ParentPanels.FindRef(Layer.ParentId);
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
                    Document.SchemaVersion);
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
                    Document.SchemaVersion);
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
                    Document.SchemaVersion);
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
            ParentPanels.Add(Layer.Id, ContentPanel);
            Result.GeneratedWidgetClasses.Add(
                Layer.Id,
                AuthoredWidget->GetClass()->GetName());
            ++Result.GeneratedWidgetCount;
        }
    }

    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        const bool bNative =
            Layer.Disposition == ETigerStudioUMGDisposition::Native;
        const bool bMaterial =
            Layer.Disposition == ETigerStudioUMGDisposition::Material;
        if ((!bNative && !bMaterial)
            || Layer.Kind == ETigerStudioUMGLayerKind::Group)
        {
            continue;
        }
        UPanelWidget* Parent = Layer.ScrollPosition == TEXT("Fixed")
            ? FixedParentPanels.FindRef(Layer.ParentId)
            : ParentPanels.FindRef(Layer.ParentId);
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
            if (Payload)
            {
                Payload->TryGetNumberField(TEXT("font_size"), FontSize);
            }
            Font.Size = FMath::Max(1, FMath::RoundToInt(FontSize));
            Text->SetFont(Font);
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

            if (bTypedImageFill && ButtonTexture
                && Layer.ImageFill.Mode == TEXT("Fit")
                && !Layer.ImageFill.NineSlice.Enabled)
            {
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
                const bool bRoundedCard =
                    Layer.Material.Schema
                        == TEXT("tigerstudio.umg.ui_material.v2")
                    && Layer.Material.Kind == TEXT("RoundedCard");
                UE_LOG(
                    LogTemp,
                    Display,
                    TEXT("TigerStudioUMG: generating UI Material for %s"),
                    *Layer.Id);
                UMaterial* Material = bRoundedCard
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
                    const FName ImageName = bRoundedCard
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
                        UCanvasPanel* MaterialHost =
                            Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
                                UCanvasPanel::StaticClass(),
                                FName(*Layer.Id));
                        MaterialHost->SetClipping(EWidgetClipping::Inherit);
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
            ConfigureWidget(Widget, Layer, Parent, Document.SchemaVersion);
            Result.GeneratedWidgetClasses.Add(
                Layer.Id,
                Widget->GetClass()->GetName());
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
        Defaults->TigerSourceProvider = Document.Provider;
        Defaults->TigerSourceDocumentId = Document.DocumentId;
        Defaults->TigerSourceRevision = Document.Revision;
        Defaults->TigerInteractions = Document.Interactions;
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
