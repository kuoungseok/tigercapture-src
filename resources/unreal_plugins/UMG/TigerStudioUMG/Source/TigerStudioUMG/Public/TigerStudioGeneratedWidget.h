#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "TigerStudioUMGTypes.h"
#include "TigerStudioGeneratedWidget.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(
    FTigerStudioWidgetInteraction,
    FName,
    ComponentId,
    FName,
    EventName);

UCLASS(Blueprintable)
class TIGERSTUDIOUMG_API UTigerStudioGeneratedWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio")
    FString TigerSourceProvider;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio")
    FString TigerSourceDocumentId;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio")
    int32 TigerSourceRevision = 0;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGInteractionRecord> TigerInteractions;

    /**
     * Concrete child-component values owned by this parent class default.
     * UMG may reconstruct foreign child templates from the child class CDO,
     * so the parent reapplies these records after its live tree is built.
     */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Tiger Studio")
    TArray<FTigerStudioUMGComponentInstanceRecord> TigerComponentInstances;

    /** Apply parent-owned values to live child component trees recursively. */
    UFUNCTION(BlueprintCallable, Category = "Tiger Studio|Component")
    void ApplyTigerComponentInstances();

    /** Refresh schema-v19 RoundedCard MID sizes from live widget geometry. */
    UFUNCTION(BlueprintCallable, Category = "Tiger Studio|Material")
    void UpdateTigerRoundedCards();

    UPROPERTY(BlueprintAssignable, Category = "Tiger Studio")
    FTigerStudioWidgetInteraction OnTigerInteraction;

    UFUNCTION(BlueprintCallable, Category = "Tiger Studio")
    void EmitTigerInteraction(FName ComponentId, FName EventName);

    UFUNCTION(BlueprintCallable, Category = "Tiger Studio")
    void ExecuteTigerInteraction(const FString& ComponentId, const FString& Trigger);

protected:
    virtual void NativePreConstruct() override;
    virtual void NativeConstruct() override;

private:
    class UWidgetAnimation* FindTigerAnimation(const FString& AnimationName) const;
};
