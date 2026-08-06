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

    /** Stable component id -> generated reusable Widget Blueprint object path. */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> GeneratedComponentAssetPaths;

    /** Stable component id -> generated Widget Blueprint class object path. */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> GeneratedComponentClassPaths;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> ImportedAssetPaths;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> GeneratedMaterialPaths;

    /**
     * Authored layer ID, or a deterministic synthetic ID such as
     * "<layer>#spacer_before", -> generated widget class name. Synthetic
     * entries are audit evidence and do not increase GeneratedWidgetCount.
     */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> GeneratedWidgetClasses;

    /**
     * Layer ID -> concise JSON describing the validated native button style
     * that was applied.  This is generation evidence, not executable input.
     */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> GeneratedButtonStyleAudit;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> GeneratedWidgetVisibilityAudit;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> Warnings;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FString> Errors;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 GeneratedWidgetCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 GeneratedComponentCount = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 GeneratedAnimationCount = 0;
};

USTRUCT(BlueprintType)
struct FTigerStudioUMGRenderResult
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    bool bSuccess = false;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    FString Message;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    FString OutputPath;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 Width = 0;

    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    int32 Height = 0;

    /** Runtime widget path -> rendered text after NativePreConstruct/Construct. */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> WidgetTextAudit;

    /** Runtime widget path -> concise ESlateVisibility name. */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> WidgetVisibilityAudit;

    /** Before/after diagnostics for parent-owned component instance replay. */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> ComponentInstanceAudit;

    /** Runtime widget path -> SizeBinding/fixed/live CardSize diagnostics. */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> RoundedCardSizeAudit;

    /** Runtime widget path -> padded visual Canvas-slot diagnostics. */
    UPROPERTY(BlueprintReadOnly, Category = "Tiger Studio")
    TMap<FString, FString> RoundedCardVisualSlotAudit;
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

    /** Render a generated Widget Blueprint through Slate without relying on OS window capture. */
    UFUNCTION(BlueprintCallable, Category = "Tiger Studio|UMG")
    FTigerStudioUMGRenderResult RenderWidgetBlueprintToPng(
        const FString& WidgetAssetPath,
        const FString& OutputPath,
        FVector2D DrawSize) const;
};
