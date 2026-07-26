#pragma once

#include "CoreMinimal.h"
#include "Components/Button.h"
#include "TigerStudioButton.generated.h"

class UTigerStudioGeneratedWidget;

UCLASS()
class TIGERSTUDIOUMG_API UTigerStudioButton : public UButton
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tiger Studio")
    FString TigerComponentId;

    void InitializeTigerButton(UTigerStudioGeneratedWidget* InOwner);

private:
    UPROPERTY(Transient)
    TObjectPtr<UTigerStudioGeneratedWidget> TigerOwner;

    UFUNCTION()
    void HandleClicked();

    UFUNCTION()
    void HandleHovered();

    UFUNCTION()
    void HandleUnhovered();

    UFUNCTION()
    void HandlePressed();

    UFUNCTION()
    void HandleReleased();
};
