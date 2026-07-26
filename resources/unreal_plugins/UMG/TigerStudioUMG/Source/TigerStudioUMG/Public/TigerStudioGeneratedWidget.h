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

    UPROPERTY(BlueprintAssignable, Category = "Tiger Studio")
    FTigerStudioWidgetInteraction OnTigerInteraction;

    UFUNCTION(BlueprintCallable, Category = "Tiger Studio")
    void EmitTigerInteraction(FName ComponentId, FName EventName);

    UFUNCTION(BlueprintCallable, Category = "Tiger Studio")
    void ExecuteTigerInteraction(const FString& ComponentId, const FString& Trigger);

protected:
    virtual void NativeConstruct() override;

private:
    class UWidgetAnimation* FindTigerAnimation(const FString& AnimationName) const;
};
