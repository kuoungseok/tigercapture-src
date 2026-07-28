#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "TigerStudioUMGTypes.h"
#include "TigerStudioUMGImportSubsystem.generated.h"

USTRUCT(BlueprintType)
struct FTigerStudioUMGPreflightResult
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    bool bSuccess = false;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    FString Message;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    FTigerStudioUMGDocumentRecord Document;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 NativeLayerCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 MaterialLayerCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 BakedLayerCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 BlockedLayerCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> BlockReasons;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 ResourceCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 InteractionCount = 0;
};

USTRUCT(BlueprintType)
struct FTigerStudioUMGGenerationResult
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    bool bSuccess = false;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    FString Message;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    FString GeneratedAssetPath;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> ImportedAssetPaths;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> Warnings;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> Errors;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 GeneratedWidgetCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 GeneratedAnimationCount = 0;
};

UCLASS()
class TIGERSTUDIOUMGEDITOR_API UTigerStudioUMGImportSubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Tiger Studio|UMG")
    FTigerStudioUMGPreflightResult PreflightDocumentFile(const FString& DocumentPath) const;

    UFUNCTION(BlueprintCallable, Category = "Tiger Studio|UMG")
    FTigerStudioUMGGenerationResult GenerateDocumentFile(
        const FString& DocumentPath,
        const FString& DestinationRoot = TEXT("/Game/TigerStudio/Generated")) const;
};
