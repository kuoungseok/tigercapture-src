#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "TigerStudioUMGTypes.generated.h"

UENUM(BlueprintType)
enum class ETigerStudioUMGLayerKind : uint8
{
    Group,
    Shape,
    Text,
    Image,
    Button,
    Baked,
    Unsupported
};

UENUM(BlueprintType)
enum class ETigerStudioUMGDisposition : uint8
{
    Native,
    Material,
    Baked,
    Blocked
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGResourceRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Kind;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString SourcePath;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString DestinationName;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ContentHash;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString SettingsJson;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGKeyframeRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 TimeMilliseconds = 0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector4 Value = FVector4(0.0, 0.0, 0.0, 0.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Interpolation = TEXT("linear");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D InTangent = FVector2D(0.667, 1.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D OutTangent = FVector2D(0.333, 0.0);
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGAnimationTrackRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString LayerId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString AnimationName = TEXT("TigerTimeline");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Property;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGKeyframeRecord> Keyframes;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGActionRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Type;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString TargetId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ResourceId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FSoftObjectPath ResourcePath;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ValueJson;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ParametersJson;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGInteractionRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ComponentId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Trigger;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGActionRecord> Actions;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGCanvasSlotRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D AnchorMinimum = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D AnchorMaximum = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FMargin Offsets = FMargin(0.0, 0.0, 100.0, 100.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Alignment = FVector2D(0.5, 0.5);
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGFlowSlotRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FMargin Padding = FMargin(0.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString HorizontalAlignment = TEXT("Fill");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString VerticalAlignment = TEXT("Fill");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString SizeRule = TEXT("Auto");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double FillCoefficient = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 Row = 0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 Column = 0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 RowSpan = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 ColumnSpan = 1;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGGradientStopRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Position = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Color = TEXT("#FFFFFFFF");
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGStrokeRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Width = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Alignment = TEXT("Inside");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Color = TEXT("#00000000");
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGShadowRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    bool Enabled = false;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Color = TEXT("#00000000");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Offset = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Blur = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Spread = 0.0;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGImageCropRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    bool Enabled = false;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Units = TEXT("Normalized");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double X = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Y = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Width = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Height = 1.0;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGImageAdjustmentsRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Exposure = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Contrast = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Saturation = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Temperature = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Tint = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Highlights = 0.0;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGImageNineSliceRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    bool Enabled = false;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Units = TEXT("Pixels");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Left = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Top = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Right = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Bottom = 0.0;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGImageFillRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString AssetId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Mode = TEXT("Stretch");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D SourceSize = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D FocalPoint = FVector2D(0.5, 0.5);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double TileScale = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGImageCropRecord Crop;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Opacity = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Tint = TEXT("#FFFFFFFF");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGImageAdjustmentsRecord Adjustments;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGImageNineSliceRecord NineSlice;

    // X/Y/Z/W = top-left/top-right/bottom-right/bottom-left in Slate units.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector4 CornerRadii = FVector4(0.0, 0.0, 0.0, 0.0);
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGMaterialRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Schema;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Generator;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Kind;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString CoordinateSpace;

    // Schema v2 rounded-card fields. They intentionally coexist with the v1
    // gradient fields below so schema v4-v7 documents continue to deserialize.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Size = FVector2D(100.0, 100.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString FillKind = TEXT("Solid");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString FillColor = TEXT("#FFFFFFFF");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector4 CornerRadii = FVector4(0.0, 0.0, 0.0, 0.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double CornerSmoothing = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGStrokeRecord Stroke;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGShadowRecord DropShadow;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGShadowRecord InnerShadow;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FMargin VisualPadding = FMargin(0.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Start = FVector2D(0.0, 0.5);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D End = FVector2D(1.0, 0.5);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Width = FVector2D(0.0, 1.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGGradientStopRecord> Stops;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Opacity = 1.0;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGLayerRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ParentId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    ETigerStudioUMGLayerKind Kind = ETigerStudioUMGLayerKind::Shape;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    ETigerStudioUMGDisposition Disposition = ETigerStudioUMGDisposition::Native;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> BlockReasons;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Position = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Size = FVector2D(100.0, 100.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Scale = FVector2D(1.0, 1.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Anchor = FVector2D(0.5, 0.5);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGCanvasSlotRecord CanvasSlot;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString PanelKind = TEXT("None");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGFlowSlotRecord FlowSlot;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ScrollOverflow = TEXT("None");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ScrollPosition = TEXT("Scroll");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D RenderTransformPivot = FVector2D(0.5, 0.5);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double RotationDegrees = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Opacity = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString AssetId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGImageFillRecord ImageFill;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGMaterialRecord Material;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString PayloadJson;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGDocumentRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 SchemaVersion = 11;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Provider;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString DocumentId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 Revision = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 Width = 1920;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 Height = 1080;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double FrameRate = 30.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 DurationMilliseconds = 5000;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGResourceRecord> Resources;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGLayerRecord> Layers;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGAnimationTrackRecord> Animations;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGInteractionRecord> Interactions;
};

UCLASS(BlueprintType)
class TIGERSTUDIOUMG_API UTigerStudioUMGDocumentAsset : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGDocumentRecord Document;
};
