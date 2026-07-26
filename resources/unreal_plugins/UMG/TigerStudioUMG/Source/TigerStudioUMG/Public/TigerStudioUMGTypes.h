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
    FVector2D Position = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Size = FVector2D(100.0, 100.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Scale = FVector2D(1.0, 1.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FVector2D Anchor = FVector2D(0.5, 0.5);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double RotationDegrees = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    double Opacity = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString AssetId;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString PayloadJson;
};

USTRUCT(BlueprintType)
struct TIGERSTUDIOUMG_API FTigerStudioUMGDocumentRecord
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    int32 SchemaVersion = 3;

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
