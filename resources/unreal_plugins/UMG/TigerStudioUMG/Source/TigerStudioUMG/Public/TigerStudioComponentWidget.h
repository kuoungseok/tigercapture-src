#pragma once

#include "CoreMinimal.h"
#include "TigerStudioGeneratedWidget.h"
#include "TigerStudioUMGTypes.h"
#include "TigerStudioComponentWidget.generated.h"

/**
 * Runtime base for schema-v18 reusable component Widget Blueprints.
 *
 * The editor generator adds strongly typed Blueprint variables. This class
 * keeps the provider-neutral target bindings and applies their static values
 * without generating fragile Blueprint graphs.
 */
UCLASS(Blueprintable)
class TIGERSTUDIOUMG_API UTigerStudioComponentWidget
    : public UTigerStudioGeneratedWidget
{
    GENERATED_BODY()

public:
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio|Component")
    FString TigerComponentId;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio|Component")
    FString TigerBaseComponentId;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio|Component")
    FString TigerVariantValuesJson;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio|Component")
    TArray<FTigerStudioUMGComponentPropertyRecord> TigerComponentProperties;

    /**
     * Canonical static values authored on this concrete child template.
     * Native storage is intentional: dynamically generated Blueprint member
     * overrides can be reconstructed from the component CDO while a parent
     * Widget Blueprint initializes its foreign child tree.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tiger Studio|Component", meta = (ExposeOnSpawn = "true"))
    FString TigerInstancePropertyValuesJson = TEXT("{}");

    /**
     * Static source-layer overrides for this concrete instance. The only
     * executable paths in schema 18 are content.text and visible.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tiger Studio|Component", meta = (ExposeOnSpawn = "true"))
    FString TigerResolvedOverridesJson = TEXT("{}");

    /** Reapply exposed/static properties after a caller changes them. */
    UFUNCTION(BlueprintCallable, Category = "Tiger Studio|Component")
    void ApplyTigerComponentProperties();

protected:
    virtual void NativePreConstruct() override;
    virtual void NativeConstruct() override;
};
