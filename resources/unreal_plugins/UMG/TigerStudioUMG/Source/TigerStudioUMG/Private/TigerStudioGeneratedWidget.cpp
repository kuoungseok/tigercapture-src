#include "TigerStudioGeneratedWidget.h"

#include "Animation/WidgetAnimation.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Image.h"
#include "Components/Widget.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "TigerStudioButton.h"
#include "TigerStudioComponentWidget.h"
#include "TigerStudioRoundedCardHost.h"

void UTigerStudioGeneratedWidget::EmitTigerInteraction(
    const FName ComponentId,
    const FName EventName)
{
    OnTigerInteraction.Broadcast(ComponentId, EventName);
}

void UTigerStudioGeneratedWidget::ApplyTigerComponentInstances()
{
    if (!WidgetTree)
    {
        return;
    }
    for (const FTigerStudioUMGComponentInstanceRecord& Instance
         : TigerComponentInstances)
    {
        UTigerStudioComponentWidget* Component =
            Cast<UTigerStudioComponentWidget>(
                WidgetTree->FindWidget(FName(*Instance.LayerId)));
        if (!Component)
        {
            continue;
        }
        const UTigerStudioComponentWidget* Defaults =
            Component->GetClass()
                ->GetDefaultObject<UTigerStudioComponentWidget>();
        if (Defaults && Defaults != Component)
        {
            // A foreign UUserWidget embedded in another generated WidgetTree
            // can reach the live tree with native definition arrays cleared,
            // even though its generated-class CDO retains them. These arrays
            // are class definition metadata, never per-instance values, so
            // always restore them from the authoritative component CDO.
            Component->TigerComponentProperties =
                Defaults->TigerComponentProperties;
            Component->TigerComponentInstances =
                Defaults->TigerComponentInstances;
            if (Component->TigerComponentId.IsEmpty())
            {
                Component->TigerComponentId = Defaults->TigerComponentId;
            }
            if (Component->TigerBaseComponentId.IsEmpty())
            {
                Component->TigerBaseComponentId =
                    Defaults->TigerBaseComponentId;
            }
            if (Component->TigerVariantValuesJson.IsEmpty())
            {
                Component->TigerVariantValuesJson =
                    Defaults->TigerVariantValuesJson;
            }
            if (Component->TigerSourceProvider.IsEmpty())
            {
                Component->TigerSourceProvider =
                    Defaults->TigerSourceProvider;
            }
            if (Component->TigerSourceDocumentId.IsEmpty())
            {
                Component->TigerSourceDocumentId =
                    Defaults->TigerSourceDocumentId;
            }
            if (Component->TigerSourceRevision <= 0)
            {
                Component->TigerSourceRevision =
                    Defaults->TigerSourceRevision;
            }
        }
        Component->TigerInstancePropertyValuesJson =
            Instance.PropertyValuesJson.IsEmpty()
                ? TEXT("{}")
                : Instance.PropertyValuesJson;
        Component->TigerResolvedOverridesJson =
            Instance.ResolvedOverridesJson.IsEmpty()
                ? TEXT("{}")
                : Instance.ResolvedOverridesJson;
        Component->ApplyTigerComponentInstances();
        Component->ApplyTigerComponentProperties();
    }
}

void UTigerStudioGeneratedWidget::NativePreConstruct()
{
    Super::NativePreConstruct();
    ApplyTigerComponentInstances();
    UpdateTigerRoundedCards();
}

void UTigerStudioGeneratedWidget::NativeConstruct()
{
    Super::NativeConstruct();
    ApplyTigerComponentInstances();
    if (!WidgetTree)
    {
        return;
    }
    WidgetTree->ForEachWidget([this](UWidget* Widget)
    {
        if (UTigerStudioButton* Button = Cast<UTigerStudioButton>(Widget))
        {
            Button->InitializeTigerButton(this);
        }
    });
    UpdateTigerRoundedCards();
}

void UTigerStudioGeneratedWidget::UpdateTigerRoundedCards()
{
    if (!WidgetTree)
    {
        return;
    }
    WidgetTree->ForEachWidget([](UWidget* Widget)
    {
        if (UTigerStudioRoundedCardHost* RoundedCard =
                Cast<UTigerStudioRoundedCardHost>(Widget))
        {
            RoundedCard->UpdateTigerMaterialSize();
        }
        if (UTigerStudioGeneratedWidget* Nested =
                Cast<UTigerStudioGeneratedWidget>(Widget))
        {
            Nested->UpdateTigerRoundedCards();
        }
    });
}

void UTigerStudioGeneratedWidget::ExecuteTigerInteraction(
    const FString& ComponentId,
    const FString& Trigger)
{
    for (const FTigerStudioUMGInteractionRecord& Interaction : TigerInteractions)
    {
        if (!Interaction.ComponentId.Equals(ComponentId, ESearchCase::CaseSensitive)
            || !Interaction.Trigger.Equals(Trigger, ESearchCase::IgnoreCase))
        {
            continue;
        }
        for (const FTigerStudioUMGActionRecord& Action : Interaction.Actions)
        {
            const FString Type = Action.Type.ToLower();
            if (Type == TEXT("emit_event"))
            {
                EmitTigerInteraction(
                    FName(*ComponentId),
                    FName(*(Action.Name.IsEmpty() ? Trigger : Action.Name)));
            }
            else if (Type == TEXT("play_animation"))
            {
                if (UWidgetAnimation* Animation = FindTigerAnimation(Action.Name))
                {
                    PlayAnimation(Animation);
                }
            }
            else if (Type == TEXT("play_sound"))
            {
                if (USoundBase* Sound = Cast<USoundBase>(Action.ResourcePath.TryLoad()))
                {
                    UGameplayStatics::PlaySound2D(this, Sound);
                }
            }
            else if (WidgetTree)
            {
                const FString TargetId = Action.TargetId.IsEmpty()
                    ? ComponentId
                    : Action.TargetId;
                if (UWidget* Target = WidgetTree->FindWidget(FName(*TargetId)))
                {
                    if (Type == TEXT("set_opacity"))
                    {
                        Target->SetRenderOpacity(FCString::Atof(*Action.ValueJson));
                    }
                    else if (Type == TEXT("set_visibility"))
                    {
                        const bool bVisible = Action.ValueJson.Equals(
                            TEXT("true"),
                            ESearchCase::IgnoreCase);
                        Target->SetVisibility(
                            bVisible ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
                    }
                    else if (Type == TEXT("set_material_scalar"))
                    {
                        UImage* Image = Cast<UImage>(Target);
                        UMaterialInstanceDynamic* Material = Image
                            ? Image->GetDynamicMaterial()
                            : nullptr;
                        if (Material)
                        {
                            Material->SetScalarParameterValue(
                                FName(*Action.Name),
                                FCString::Atof(*Action.ValueJson));
                        }
                    }
                }
            }
        }
    }
}

UWidgetAnimation* UTigerStudioGeneratedWidget::FindTigerAnimation(
    const FString& AnimationName) const
{
    const UWidgetBlueprintGeneratedClass* WidgetClass =
        Cast<UWidgetBlueprintGeneratedClass>(GetClass());
    if (!WidgetClass)
    {
        return nullptr;
    }
    for (UWidgetAnimation* Animation : WidgetClass->Animations)
    {
        if (Animation
            && Animation->GetName().Equals(AnimationName, ESearchCase::IgnoreCase))
        {
            return Animation;
        }
    }
    return nullptr;
}
