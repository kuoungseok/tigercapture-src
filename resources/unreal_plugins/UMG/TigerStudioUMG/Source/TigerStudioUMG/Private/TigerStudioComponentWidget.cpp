#include "TigerStudioComponentWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Components/TextBlock.h"
#include "Components/Widget.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"

namespace
{
FName TigerComponentVariableName(const FString& Input)
{
    FString Result;
    for (const TCHAR Character : Input)
    {
        Result.AppendChar(
            FChar::IsAlnum(Character) || Character == TEXT('_')
                ? Character
                : TEXT('_'));
    }
    if (Result.IsEmpty() || FChar::IsDigit(Result[0]))
    {
        Result = TEXT("Property_") + Result;
    }
    return FName(*Result);
}
}

void UTigerStudioComponentWidget::NativePreConstruct()
{
    Super::NativePreConstruct();
    ApplyTigerComponentProperties();
}

void UTigerStudioComponentWidget::NativeConstruct()
{
    Super::NativeConstruct();
    ApplyTigerComponentProperties();
}

void UTigerStudioComponentWidget::ApplyTigerComponentProperties()
{
    if (!WidgetTree)
    {
        return;
    }

    // A generated component's Blueprint member variables remain useful for
    // exposed/default authoring. However, when a generated component is used
    // as a foreign child template in another Widget Blueprint, UMG can rebuild
    // those dynamically added members from the component CDO while it creates
    // the live widget. Preserve imported per-instance values in a native
    // property and prefer them whenever that canonical map contains the key.
    TSharedPtr<FJsonObject> InstancePropertyValues;
    const TSharedRef<TJsonReader<>> InstanceReader =
        TJsonReaderFactory<>::Create(TigerInstancePropertyValuesJson);
    if (!FJsonSerializer::Deserialize(InstanceReader, InstancePropertyValues)
        || !InstancePropertyValues)
    {
        InstancePropertyValues.Reset();
    }

    for (const FTigerStudioUMGComponentPropertyRecord& PropertyRecord
         : TigerComponentProperties)
    {
        const FName VariableName = TigerComponentVariableName(PropertyRecord.Name);
        const FProperty* Property = GetClass()->FindPropertyByName(VariableName);
        const TSharedPtr<FJsonValue> InstanceValue = InstancePropertyValues
            ? InstancePropertyValues->TryGetField(PropertyRecord.Name)
            : nullptr;

        for (const FTigerStudioUMGComponentPropertyBindingRecord& Binding
             : PropertyRecord.Bindings)
        {
            UWidget* Target = WidgetTree->FindWidget(FName(*Binding.LayerId));
            if (!Target)
            {
                continue;
            }

            if (Binding.TargetPath.Equals(
                    TEXT("content.text"),
                    ESearchCase::IgnoreCase))
            {
                const FTextProperty* TextProperty = CastField<FTextProperty>(Property);
                UTextBlock* TextBlock = Cast<UTextBlock>(Target);
                FString StaticValue;
                if (TextBlock && InstanceValue
                    && InstanceValue->TryGetString(StaticValue))
                {
                    TextBlock->SetText(FText::FromString(StaticValue));
                }
                else if (TextProperty && TextBlock)
                {
                    TextBlock->SetText(
                        TextProperty->GetPropertyValue_InContainer(this));
                }
            }
            else if (Binding.TargetPath.Equals(
                         TEXT("visible"),
                         ESearchCase::IgnoreCase))
            {
                const FBoolProperty* BoolProperty = CastField<FBoolProperty>(Property);
                bool bStaticVisible = false;
                if (InstanceValue
                    && InstanceValue->TryGetBool(bStaticVisible))
                {
                    Target->SetVisibility(
                        bStaticVisible
                            ? ESlateVisibility::Visible
                            : ESlateVisibility::Collapsed);
                }
                else if (BoolProperty)
                {
                    Target->SetVisibility(
                        BoolProperty->GetPropertyValue_InContainer(this)
                            ? ESlateVisibility::Visible
                            : ESlateVisibility::Collapsed);
                }
            }
        }
    }

    TSharedPtr<FJsonObject> ResolvedOverrides;
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(TigerResolvedOverridesJson);
    if (!FJsonSerializer::Deserialize(Reader, ResolvedOverrides)
        || !ResolvedOverrides)
    {
        return;
    }
    for (const TPair<FString, TSharedPtr<FJsonValue>>& LayerPair
         : ResolvedOverrides->Values)
    {
        const TSharedPtr<FJsonObject> Changes = LayerPair.Value
            ? LayerPair.Value->AsObject()
            : nullptr;
        UWidget* Target = WidgetTree->FindWidget(FName(*LayerPair.Key));
        if (!Changes || !Target)
        {
            continue;
        }
        for (const TPair<FString, TSharedPtr<FJsonValue>>& Change
             : Changes->Values)
        {
            if (Change.Key == TEXT("content.text"))
            {
                FString Value;
                if (UTextBlock* Text = Cast<UTextBlock>(Target);
                    Text && Change.Value && Change.Value->TryGetString(Value))
                {
                    Text->SetText(FText::FromString(Value));
                }
            }
            else if (Change.Key == TEXT("visible"))
            {
                bool bVisible = false;
                if (Change.Value && Change.Value->TryGetBool(bVisible))
                {
                    Target->SetVisibility(
                        bVisible
                            ? ESlateVisibility::Visible
                            : ESlateVisibility::Collapsed);
                }
            }
        }
    }
}
