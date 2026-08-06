#pragma once

#include "CoreMinimal.h"
#include "Components/CanvasPanel.h"
#include "TigerStudioRoundedCardHost.generated.h"

class UMaterialInstanceDynamic;

/**
 * Stable layout host for generated RoundedCard materials.
 *
 * FixedSize keeps the original generated surface unchanged. WidgetGeometry
 * follows the live Canvas/flow allocation and updates both the padded visual
 * slot and the CardSize material parameter without replacing the layer widget.
 */
UCLASS()
class TIGERSTUDIOUMG_API UTigerStudioRoundedCardHost : public UCanvasPanel
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio|Material")
    FString TigerSizeBinding = TEXT("FixedSize");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio|Material")
    FVector2D TigerFixedCardSize = FVector2D(100.0, 100.0);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio|Material")
    FMargin TigerVisualPadding = FMargin(0.0);

    /** Last non-zero live card size applied to the MID; exposed for QA. */
    UPROPERTY(Transient, BlueprintReadOnly, Category = "Tiger Studio|Material")
    FVector2D TigerLastAppliedCardSize = FVector2D::ZeroVector;

    UFUNCTION(BlueprintCallable, Category = "Tiger Studio|Material")
    void UpdateTigerMaterialSize();

    /** Called by the matching Slate host with this frame's logical size. */
    void UpdateTigerMaterialSizeForGeometry(const FVector2D& CardSize);

    bool TryGetTigerMaterialCardSize(FVector2D& OutSize);

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;

private:
    UPROPERTY(Transient)
    TObjectPtr<UMaterialInstanceDynamic> TigerMaterialInstance;
};
