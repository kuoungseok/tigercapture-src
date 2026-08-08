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

    // FixedSize preserves schema-v8 behavior. WidgetGeometry (schema 19+)
    // updates CardSize from the live UMG layout geometry at runtime.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString SizeBinding = TEXT("FixedSize");

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

/**
 * Bounded row-major atlas selector used by the fixed Tiger flipbook UI
 * material generator.  The document never carries executable HLSL.
 */
USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGFlipbookRecord
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

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString AssetId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 Columns = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 Rows = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 FrameCount = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double FramesPerSecond = 12.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 StartFrame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    bool Loop = true;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Phase = 0.0;

    // -1 animates from Time; 0..FrameCount-1 selects a deterministic frame.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 StaticFrameOverride = -1;
};

/**
 * One visual state in the provider-neutral native UButton style contract.
 * Font metrics are carried per state so unsupported runtime-varying metrics
 * can be rejected instead of being silently flattened by Slate.
 */
USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGButtonStateRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Fill = TEXT("#4A4A4AFF");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Stroke = TEXT("#777777FF");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double StrokeWidth = 1.0;

    // X/Y/Z/W = top-left/top-right/bottom-right/bottom-left.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector4 CornerRadii = FVector4(2.0, 2.0, 2.0, 2.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString TextColor = TEXT("#FFFFFFFF");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double FontSize = 24.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 FontWeight = 700;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Opacity = 1.0;
};

/**
 * Schema-v16 typed ButtonStyle.  The four records map directly to the native
 * FButtonStyle state brushes and foreground colors during generation.
 */
USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGButtonStyleRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Schema;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    bool Enabled = true;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGButtonStateRecord Normal;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGButtonStateRecord Hovered;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGButtonStateRecord Pressed;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGButtonStateRecord Disabled;
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

    /** Schema 17 panel spacing: legacy slot margins or native linear spacers. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString SpacingStrategy = TEXT("Padding");

    /** Size rule used by synthetic USpacer slots when SpacingStrategy=Spacer. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString SpacerSizeRule = TEXT("Auto");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double SpacerFillCoefficient = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ScrollOverflow = TEXT("None");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ScrollPosition = TEXT("Scroll");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Visibility = TEXT("Visible");

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
    FTigerStudioUMGFlipbookRecord Flipbook;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGButtonStyleRecord ButtonStyle;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString PayloadJson;
};

/** One supported component property target inside a generated component WBP. */
USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGComponentPropertyBindingRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString LayerId;

    /** Provider-neutral property path such as content.text or visible. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString TargetPath;
};

/** Schema-v18 strongly typed authoring property for a reusable component. */
USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGComponentPropertyRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Name;

    /** text, boolean, number, enum, instance_swap, or slot. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Type;

    /** Canonical JSON scalar. It is never evaluated as code. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString DefaultValueJson;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> Values;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Description;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGComponentPropertyBindingRecord> Bindings;
};

/** A Figma/Painter Slot exposed as one native UMG Named Slot. */
USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGComponentSlotRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString LayerId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    bool ExposeOnInstanceOnly = true;
};

/** One reusable component (or one member of a component variant family). */
USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGComponentRecord
{
    GENERATED_BODY()

    /** Stable provider component id; it also owns the generated asset path. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString RootLayerId;

    /** Empty for a family root, otherwise the stable family component id. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString BaseComponentId;

    /** Canonical JSON object recording this member's static variant tuple. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString VariantValuesJson;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> DependencyComponentIds;

    /** Definition-local layers. They are not duplicated in screen Layers. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGLayerRecord> Layers;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGComponentPropertyRecord> Properties;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGComponentSlotRecord> Slots;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGComponentSlotContentRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString SlotName;

    /** Each root is grafted under one generated wrapper when there are many. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> RootLayerIds;
};

/** One reusable component placed in a screen Widget Blueprint. */
USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGComponentInstanceRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ComponentId;

    /** Screen placeholder layer whose layout hosts the child UUserWidget. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString LayerId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ParentId;

    /** Canonical JSON object keyed by component property name. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString PropertyValuesJson;

    /** Canonical source-layer path/value overrides retained for diagnostics. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString ResolvedOverridesJson;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGComponentSlotContentRecord> SlotContents;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGDocumentRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 SchemaVersion = 19;

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
    TArray<FTigerStudioUMGComponentRecord> Components;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGComponentInstanceRecord> ComponentInstances;

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
