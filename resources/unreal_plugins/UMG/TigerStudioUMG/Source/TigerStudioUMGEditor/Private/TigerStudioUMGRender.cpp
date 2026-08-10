#include "TigerStudioUMGImportSubsystem.h"

#include "AssetCompilingManager.h"
#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Button.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "ContentStreaming.h"
#include "Editor.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "ImageUtils.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Rendering/Texture2DResource.h"
#include "Slate/WidgetRenderer.h"
#include "TigerStudioComponentWidget.h"
#include "TigerStudioGeneratedWidget.h"
#include "TigerStudioRoundedCardHost.h"
#include "Widgets/SWidget.h"

namespace
{
FString NormalizeWidgetObjectPath(const FString& AssetPath)
{
    FString Result = AssetPath.TrimStartAndEnd();
    if (Result.IsEmpty() || Result.Contains(TEXT(".")))
    {
        return Result;
    }

    const FString AssetName = FPaths::GetBaseFilename(Result);
    return FString::Printf(TEXT("%s.%s"), *Result, *AssetName);
}

void PrepareBrushResources(
    const FSlateBrush& Brush,
    TArray<UTexture2D*>& Textures,
    TArray<UMaterialInterface*>& Materials)
{
    if (UTexture2D* Texture = Cast<UTexture2D>(Brush.GetResourceObject()))
    {
        Textures.AddUnique(Texture);
    }
    else if (UMaterialInterface* Material = Cast<UMaterialInterface>(
                 Brush.GetResourceObject()))
    {
        Materials.AddUnique(Material);
    }
}

void CollectWidgetBrushResources(
    UUserWidget* Widget,
    TArray<UTexture2D*>& Textures,
    TArray<UMaterialInterface*>& Materials,
    TSet<const UUserWidget*>& VisitedOwners)
{
    if (!Widget
        || !Widget->WidgetTree
        || VisitedOwners.Contains(Widget))
    {
        return;
    }
    VisitedOwners.Add(Widget);
    Widget->WidgetTree->ForEachWidget(
        [&Textures, &Materials, &VisitedOwners](UWidget* Child)
    {
        if (const UImage* Image = Cast<UImage>(Child))
        {
            PrepareBrushResources(Image->GetBrush(), Textures, Materials);
        }
        if (const UButton* Button = Cast<UButton>(Child))
        {
            const FButtonStyle& Style = Button->GetStyle();
            PrepareBrushResources(Style.Normal, Textures, Materials);
            PrepareBrushResources(Style.Hovered, Textures, Materials);
            PrepareBrushResources(Style.Pressed, Textures, Materials);
            PrepareBrushResources(Style.Disabled, Textures, Materials);
        }
        if (UUserWidget* Nested = Cast<UUserWidget>(Child))
        {
            CollectWidgetBrushResources(
                Nested,
                Textures,
                Materials,
                VisitedOwners);
        }
    });
}

void PrepareWidgetTextures(UUserWidget* Widget)
{
    TArray<UTexture2D*> Textures;
    TArray<UMaterialInterface*> Materials;
    TSet<const UUserWidget*> VisitedOwners;
    CollectWidgetBrushResources(
        Widget,
        Textures,
        Materials,
        VisitedOwners);

    FAssetCompilingManager::Get().FinishAllCompilation();
    for (UMaterialInterface* Material : Materials)
    {
        // Generated UI materials may load before their complete Slate shader
        // map or their default texture parameters are resident. This critical
        // evidence path must wait instead of capturing a transparent fallback.
        Material->EnsureIsComplete();
        TArray<UTexture*> UsedTextures;
        Material->GetUsedTextures(UsedTextures);
        for (UTexture* UsedTexture : UsedTextures)
        {
            if (UTexture2D* Texture = Cast<UTexture2D>(UsedTexture))
            {
                Textures.AddUnique(Texture);
            }
        }
    }
    FAssetCompilingManager::Get().FinishAllCompilation();
    for (UTexture2D* Texture : Textures)
    {
        Texture->SetForceMipLevelsToBeResident(30.0f);
        Texture->UpdateResource();
    }
    FAssetCompilingManager::Get().FinishAllCompilation();
    for (UTexture2D* Texture : Textures)
    {
        Texture->WaitForStreaming();
    }
    IStreamingManager::Get().StreamAllResources(10.0f);
    FlushRenderingCommands();
}

FString VisibilityAuditName(const ESlateVisibility Visibility)
{
    switch (Visibility)
    {
    case ESlateVisibility::Collapsed:
        return TEXT("Collapsed");
    case ESlateVisibility::Hidden:
        return TEXT("Hidden");
    case ESlateVisibility::HitTestInvisible:
        return TEXT("HitTestInvisible");
    case ESlateVisibility::SelfHitTestInvisible:
        return TEXT("SelfHitTestInvisible");
    case ESlateVisibility::Visible:
    default:
        return TEXT("Visible");
    }
}

FString ComponentAuditOwnerKey(
    const FString& Phase,
    const FString& OwnerPath)
{
    return Phase + TEXT("/")
        + (OwnerPath.IsEmpty() ? TEXT("root") : OwnerPath);
}

void CollectComponentInstanceAudit(
    UTigerStudioGeneratedWidget* Owner,
    const FString& Phase,
    const FString& OwnerPath,
    TMap<FString, FString>& Audit,
    TSet<const UTigerStudioGeneratedWidget*>& VisitedOwners)
{
    if (!Owner || VisitedOwners.Contains(Owner))
    {
        return;
    }
    VisitedOwners.Add(Owner);

    const FString OwnerKey = ComponentAuditOwnerKey(Phase, OwnerPath);
    Audit.Add(OwnerKey + TEXT("/owner_class"), Owner->GetClass()->GetPathName());
    Audit.Add(
        OwnerKey + TEXT("/record_count"),
        FString::FromInt(Owner->TigerComponentInstances.Num()));
    Audit.Add(
        OwnerKey + TEXT("/widget_tree"),
        Owner->WidgetTree ? TEXT("true") : TEXT("false"));
    if (!Owner->WidgetTree)
    {
        return;
    }

    for (int32 InstanceIndex = 0;
         InstanceIndex < Owner->TigerComponentInstances.Num();
         ++InstanceIndex)
    {
        const FTigerStudioUMGComponentInstanceRecord& Instance =
            Owner->TigerComponentInstances[InstanceIndex];
        const FString RecordKey = FString::Printf(
            TEXT("%s/record[%d]:%s"),
            *OwnerKey,
            InstanceIndex,
            *Instance.LayerId);
        Audit.Add(RecordKey + TEXT("/component_id"), Instance.ComponentId);
        Audit.Add(
            RecordKey + TEXT("/record_property_values_json"),
            Instance.PropertyValuesJson);
        Audit.Add(
            RecordKey + TEXT("/record_resolved_overrides_json"),
            Instance.ResolvedOverridesJson);

        UWidget* FoundWidget =
            Owner->WidgetTree->FindWidget(FName(*Instance.LayerId));
        Audit.Add(
            RecordKey + TEXT("/find_widget"),
            FoundWidget ? TEXT("true") : TEXT("false"));
        Audit.Add(
            RecordKey + TEXT("/widget_class"),
            FoundWidget ? FoundWidget->GetClass()->GetPathName() : TEXT(""));
        UTigerStudioComponentWidget* Component =
            Cast<UTigerStudioComponentWidget>(FoundWidget);
        Audit.Add(
            RecordKey + TEXT("/cast_component"),
            Component ? TEXT("true") : TEXT("false"));
        if (!Component)
        {
            continue;
        }

        Audit.Add(
            RecordKey + TEXT("/child_instance_property_values_json"),
            Component->TigerInstancePropertyValuesJson);
        Audit.Add(
            RecordKey + TEXT("/child_resolved_overrides_json"),
            Component->TigerResolvedOverridesJson);
        Audit.Add(
            RecordKey + TEXT("/child_property_count"),
            FString::FromInt(Component->TigerComponentProperties.Num()));
        Audit.Add(
            RecordKey + TEXT("/child_widget_tree"),
            Component->WidgetTree ? TEXT("true") : TEXT("false"));

        for (int32 PropertyIndex = 0;
             PropertyIndex < Component->TigerComponentProperties.Num();
             ++PropertyIndex)
        {
            const FTigerStudioUMGComponentPropertyRecord& Property =
                Component->TigerComponentProperties[PropertyIndex];
            const FString PropertyKey = FString::Printf(
                TEXT("%s/property[%d]:%s"),
                *RecordKey,
                PropertyIndex,
                *Property.Name);
            Audit.Add(PropertyKey + TEXT("/type"), Property.Type);
            Audit.Add(
                PropertyKey + TEXT("/binding_count"),
                FString::FromInt(Property.Bindings.Num()));
            for (int32 BindingIndex = 0;
                 BindingIndex < Property.Bindings.Num();
                 ++BindingIndex)
            {
                const FTigerStudioUMGComponentPropertyBindingRecord& Binding =
                    Property.Bindings[BindingIndex];
                const FString BindingKey = FString::Printf(
                    TEXT("%s/binding[%d]:%s:%s"),
                    *PropertyKey,
                    BindingIndex,
                    *Binding.LayerId,
                    *Binding.TargetPath);
                UWidget* Target = Component->WidgetTree
                    ? Component->WidgetTree->FindWidget(
                        FName(*Binding.LayerId))
                    : nullptr;
                Audit.Add(
                    BindingKey + TEXT("/target_found"),
                    Target ? TEXT("true") : TEXT("false"));
                Audit.Add(
                    BindingKey + TEXT("/target_class"),
                    Target ? Target->GetClass()->GetPathName() : TEXT(""));
                if (Binding.TargetPath.Equals(
                        TEXT("content.text"),
                        ESearchCase::IgnoreCase))
                {
                    const UTextBlock* Text = Cast<UTextBlock>(Target);
                    Audit.Add(
                        BindingKey + TEXT("/current_text"),
                        Text ? Text->GetText().ToString() : TEXT("<not_text>"));
                }
                else if (Binding.TargetPath.Equals(
                             TEXT("visible"),
                             ESearchCase::IgnoreCase))
                {
                    Audit.Add(
                        BindingKey + TEXT("/current_visibility"),
                        Target
                            ? VisibilityAuditName(Target->GetVisibility())
                            : TEXT("<missing>"));
                }
            }
        }

        const FString ChildPath = OwnerPath.IsEmpty()
            ? Instance.LayerId
            : OwnerPath + TEXT("/") + Instance.LayerId;
        CollectComponentInstanceAudit(
            Component,
            Phase,
            ChildPath,
            Audit,
            VisitedOwners);
    }
}

void CollectWidgetRuntimeAudit(
    UUserWidget* Owner,
    const FString& Prefix,
    TMap<FString, FString>& TextAudit,
    TMap<FString, FString>& VisibilityAudit,
    TSet<const UUserWidget*>& VisitedOwners)
{
    if (!Owner || !Owner->WidgetTree || VisitedOwners.Contains(Owner))
    {
        return;
    }
    VisitedOwners.Add(Owner);

    Owner->WidgetTree->ForEachWidget(
        [&Prefix, &TextAudit, &VisibilityAudit, &VisitedOwners](UWidget* Child)
        {
            if (!Child)
            {
                return;
            }
            const FString Name = Child->GetFName().ToString();
            const FString Path = Prefix.IsEmpty()
                ? Name
                : Prefix + TEXT("/") + Name;
            VisibilityAudit.Add(
                Path,
                VisibilityAuditName(Child->GetVisibility()));
            if (const UTextBlock* Text = Cast<UTextBlock>(Child))
            {
                TextAudit.Add(Path, Text->GetText().ToString());
            }
            if (UUserWidget* Nested = Cast<UUserWidget>(Child))
            {
                CollectWidgetRuntimeAudit(
                    Nested,
                    Path,
                    TextAudit,
                    VisibilityAudit,
                    VisitedOwners);
            }
        });
}

void CollectWidgetGeometryAudit(
    UUserWidget* Owner,
    const FString& Prefix,
    TMap<FString, FString>& GeometryAudit,
    TSet<const UUserWidget*>& VisitedOwners)
{
    if (!Owner || !Owner->WidgetTree || VisitedOwners.Contains(Owner))
    {
        return;
    }
    VisitedOwners.Add(Owner);
    Owner->WidgetTree->ForEachWidget(
        [&Prefix, &GeometryAudit, &VisitedOwners](UWidget* Child)
        {
            if (!Child)
            {
                return;
            }
            const FString Name = Child->GetFName().ToString();
            const FString Path = Prefix.IsEmpty()
                ? Name
                : Prefix + TEXT("/") + Name;
            const FGeometry& Geometry = Child->GetCachedGeometry();
            const FVector2D AbsPos =
                Geometry.GetAbsolutePosition();
            const FVector2D LocalSize = Geometry.GetLocalSize();
            GeometryAudit.Add(
                Path,
                FString::Printf(
                    TEXT("abspos=%.2f,%.2f;localsize=%.2fx%.2f"),
                    AbsPos.X,
                    AbsPos.Y,
                    LocalSize.X,
                    LocalSize.Y));
            if (UUserWidget* Nested = Cast<UUserWidget>(Child))
            {
                CollectWidgetGeometryAudit(
                    Nested,
                    Path,
                    GeometryAudit,
                    VisitedOwners);
            }
        });
}

void CollectRoundedCardRuntimeAudit(
    UUserWidget* Owner,
    const FString& Prefix,
    TMap<FString, FString>& SizeAudit,
    TMap<FString, FString>& VisualSlotAudit,
    TSet<const UUserWidget*>& VisitedOwners)
{
    if (!Owner || !Owner->WidgetTree || VisitedOwners.Contains(Owner))
    {
        return;
    }
    VisitedOwners.Add(Owner);
    Owner->WidgetTree->ForEachWidget(
        [&Prefix, &SizeAudit, &VisualSlotAudit, &VisitedOwners](UWidget* Child)
        {
            if (!Child)
            {
                return;
            }
            const FString Name = Child->GetFName().ToString();
            const FString Path = Prefix.IsEmpty()
                ? Name
                : Prefix + TEXT("/") + Name;
            if (UTigerStudioRoundedCardHost* Host =
                    Cast<UTigerStudioRoundedCardHost>(Child))
            {
                FVector2D MidSize = FVector2D::ZeroVector;
                const bool bHasMidSize =
                    Host->TryGetTigerMaterialCardSize(MidSize);
                const FString MidValue = bHasMidSize
                    ? FString::Printf(
                        TEXT("%.3fx%.3f"),
                        MidSize.X,
                        MidSize.Y)
                    : TEXT("unavailable");
                const FVector2D GeometrySize =
                    Host->GetCachedGeometry().GetLocalSize();
                SizeAudit.Add(
                    Path,
                    FString::Printf(
                        TEXT("binding=%s;fixed=%.3fx%.3f;geometry=%.3fx%.3f;live=%.3fx%.3f;mid=%s"),
                        *Host->TigerSizeBinding,
                        Host->TigerFixedCardSize.X,
                        Host->TigerFixedCardSize.Y,
                        GeometrySize.X,
                        GeometrySize.Y,
                        Host->TigerLastAppliedCardSize.X,
                        Host->TigerLastAppliedCardSize.Y,
                        *MidValue));
                UImage* Visual = Host->GetChildrenCount() > 0
                    ? Cast<UImage>(Host->GetChildAt(0))
                    : nullptr;
                UCanvasPanelSlot* Slot = Visual
                    ? Cast<UCanvasPanelSlot>(Visual->Slot)
                    : nullptr;
                const FVector2D Position = Slot
                    ? Slot->GetPosition()
                    : FVector2D::ZeroVector;
                const FVector2D Size = Slot
                    ? Slot->GetSize()
                    : FVector2D::ZeroVector;
                VisualSlotAudit.Add(
                    Path,
                    FString::Printf(
                        TEXT("position=%.3f,%.3f;size=%.3fx%.3f;padding=%.3f,%.3f,%.3f,%.3f"),
                        Position.X,
                        Position.Y,
                        Size.X,
                        Size.Y,
                        Host->TigerVisualPadding.Left,
                        Host->TigerVisualPadding.Top,
                        Host->TigerVisualPadding.Right,
                        Host->TigerVisualPadding.Bottom));
            }
            if (UUserWidget* Nested = Cast<UUserWidget>(Child))
            {
                CollectRoundedCardRuntimeAudit(
                    Nested,
                    Path,
                    SizeAudit,
                    VisualSlotAudit,
                    VisitedOwners);
            }
        });
}
}

FTigerStudioUMGRenderResult
UTigerStudioUMGImportSubsystem::RenderWidgetBlueprintToPng(
    const FString& WidgetAssetPath,
    const FString& OutputPath,
    FVector2D DrawSize) const
{
    FTigerStudioUMGRenderResult Result;
    Result.Width = FMath::RoundToInt(DrawSize.X);
    Result.Height = FMath::RoundToInt(DrawSize.Y);
    Result.OutputPath = FPaths::ConvertRelativePathToFull(OutputPath);

    if (Result.Width <= 0 || Result.Height <= 0)
    {
        Result.Message = TEXT("DrawSize must be positive.");
        return Result;
    }

    const FString ObjectPath = NormalizeWidgetObjectPath(WidgetAssetPath);
    UClass* WidgetClass = LoadObject<UClass>(
        nullptr,
        *FString::Printf(TEXT("%s_C"), *ObjectPath));
    if (!WidgetClass || !WidgetClass->IsChildOf(UUserWidget::StaticClass()))
    {
        Result.Message = FString::Printf(
            TEXT("Generated UserWidget class could not be loaded: %s"),
            *ObjectPath);
        return Result;
    }

    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World)
    {
        Result.Message = TEXT("Editor world is unavailable.");
        return Result;
    }

    UUserWidget* Widget = CreateWidget<UUserWidget>(World, WidgetClass);
    if (!Widget)
    {
        Result.Message = TEXT("UserWidget instance could not be created.");
        return Result;
    }

    const FVector2D PixelSize(Result.Width, Result.Height);
    const TSharedRef<SWidget> SlateWidget = Widget->TakeWidget();
    UTigerStudioGeneratedWidget* GeneratedWidget =
        Cast<UTigerStudioGeneratedWidget>(Widget);
    if (GeneratedWidget)
    {
        TSet<const UTigerStudioGeneratedWidget*> VisitedBeforeOwners;
        CollectComponentInstanceAudit(
            GeneratedWidget,
            TEXT("before"),
            TEXT(""),
            Result.ComponentInstanceAudit,
            VisitedBeforeOwners);
        // TakeWidget is sufficient for offscreen Slate rendering but does not
        // guarantee NativeConstruct. Apply the parent-owned instance records
        // explicitly before both semantic audit and raster capture.
        GeneratedWidget->ApplyTigerComponentInstances();
        TSet<const UTigerStudioGeneratedWidget*> VisitedAfterOwners;
        CollectComponentInstanceAudit(
            GeneratedWidget,
            TEXT("after"),
            TEXT(""),
            Result.ComponentInstanceAudit,
            VisitedAfterOwners);
    }
    TSet<const UUserWidget*> VisitedAuditOwners;
    CollectWidgetRuntimeAudit(
        Widget,
        TEXT(""),
        Result.WidgetTextAudit,
        Result.WidgetVisibilityAudit,
        VisitedAuditOwners);
    PrepareWidgetTextures(Widget);
    SlateWidget->SlatePrepass(1.0f);

    // Keep Slate's shader path linear, but supply a target whose RHI resource
    // is sRGB so the GPU performs exactly one output transfer. Passing false
    // to DrawWidget's implicit target factory creates a force-linear UNorm
    // target; passing true to CreateTargetFor here selects the sRGB resource
    // independently of the gamma-disabled renderer.
    FWidgetRenderer Renderer(false, true);
    UTextureRenderTarget2D* RenderTarget = FWidgetRenderer::CreateTargetFor(
        PixelSize,
        TF_Bilinear,
        true);
    if (!RenderTarget)
    {
        Result.Message = TEXT("FWidgetRenderer did not create a render target.");
        return Result;
    }
    // This is intentionally a single-pass proof. The custom Slate host applies
    // this draw's AllottedGeometry before its visual child paints; a warm-up
    // pass would hide a first-frame regression in that same-frame contract.
    Renderer.DrawWidget(RenderTarget, SlateWidget, PixelSize, 0.0f, false);

    TSet<const UUserWidget*> VisitedGeometryOwners;
    CollectWidgetGeometryAudit(
        Widget,
        TEXT(""),
        Result.WidgetGeometryAudit,
        VisitedGeometryOwners);

    TSet<const UUserWidget*> VisitedRoundedCardOwners;
    CollectRoundedCardRuntimeAudit(
        Widget,
        TEXT(""),
        Result.RoundedCardSizeAudit,
        Result.RoundedCardVisualSlotAudit,
        VisitedRoundedCardOwners);

    FlushRenderingCommands();
    FTextureRenderTargetResource* Resource =
        RenderTarget->GameThread_GetRenderTargetResource();
    TArray<FColor> Pixels;
    FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
    ReadFlags.SetLinearToGamma(false);
    if (!Resource || !Resource->ReadPixels(Pixels, ReadFlags)
        || Pixels.Num() != Result.Width * Result.Height)
    {
        Result.Message = TEXT("Rendered widget pixels could not be read.");
        return Result;
    }

    TArray64<uint8> Compressed;
    FImageUtils::PNGCompressImageArray(
        Result.Width,
        Result.Height,
        TArrayView64<const FColor>(Pixels.GetData(), Pixels.Num()),
        Compressed);
    if (Compressed.IsEmpty())
    {
        Result.Message = TEXT("Rendered widget pixels could not be compressed.");
        return Result;
    }

    IFileManager::Get().MakeDirectory(
        *FPaths::GetPath(Result.OutputPath),
        true);
    if (!FFileHelper::SaveArrayToFile(Compressed, *Result.OutputPath))
    {
        Result.Message = FString::Printf(
            TEXT("Rendered PNG could not be saved: %s"),
            *Result.OutputPath);
        return Result;
    }

    Result.bSuccess = true;
    Result.Message = FString::Printf(
        TEXT("Rendered %d x %d Widget Blueprint PNG."),
        Result.Width,
        Result.Height);
    return Result;
}
