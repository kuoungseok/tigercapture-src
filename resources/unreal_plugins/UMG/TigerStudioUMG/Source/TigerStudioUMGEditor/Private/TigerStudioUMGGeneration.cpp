#include "TigerStudioUMGImportSubsystem.h"

#include "Animation/MovieScene2DTransformSection.h"
#include "Animation/MovieScene2DTransformTrack.h"
#include "Animation/WidgetAnimation.h"
#include "AssetImportTask.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetToolsModule.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/PanelWidget.h"
#include "Components/TextBlock.h"
#include "WidgetBlueprintFactory.h"
#include "IAssetTools.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "MovieScene.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sections/MovieSceneFloatSection.h"
#include "TigerStudioButton.h"
#include "TigerStudioGeneratedWidget.h"
#include "Tracks/MovieSceneFloatTrack.h"
#include "UObject/SavePackage.h"
#include "WidgetBlueprint.h"

namespace
{
FString SafeObjectName(const FString& Input)
{
    FString Result;
    for (const TCHAR Character : Input)
    {
        Result.AppendChar(
            FChar::IsAlnum(Character) || Character == TEXT('_')
                ? Character
                : TEXT('_'));
    }
    return Result.IsEmpty() ? TEXT("Document") : Result;
}

TSharedPtr<FJsonObject> ParsePayload(const FString& Payload)
{
    TSharedPtr<FJsonObject> Result;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Payload);
    FJsonSerializer::Deserialize(Reader, Result);
    return Result;
}

FLinearColor PayloadColor(
    const TSharedPtr<FJsonObject>& Payload,
    const TCHAR* Field,
    const FLinearColor& Fallback)
{
    FString Hex;
    if (!Payload || !Payload->TryGetStringField(Field, Hex))
    {
        return Fallback;
    }
    Hex.RemoveFromStart(TEXT("#"));
    return FLinearColor(FColor::FromHex(Hex));
}

void AddKey(
    FMovieSceneFloatChannel& Channel,
    const FTigerStudioUMGKeyframeRecord& Key,
    const float Value)
{
    const FFrameNumber Time(Key.TimeMilliseconds);
    const FString Interpolation = Key.Interpolation.ToLower();
    if (Interpolation == TEXT("constant") || Interpolation == TEXT("hold"))
    {
        Channel.AddConstantKey(Time, Value);
    }
    else if (Interpolation == TEXT("linear"))
    {
        Channel.AddLinearKey(Time, Value);
    }
    else
    {
        Channel.AddCubicKey(Time, Value);
    }
}

bool SaveAssetPackage(UObject* Asset)
{
    if (!Asset)
    {
        return false;
    }
    UPackage* Package = Asset->GetOutermost();
    const FString Filename = FPackageName::LongPackageNameToFilename(
        Package->GetName(),
        FPackageName::GetAssetPackageExtension());
    FSavePackageArgs Args;
    Args.TopLevelFlags = RF_Public | RF_Standalone;
    Args.SaveFlags = SAVE_NoError;
    return UPackage::SavePackage(Package, Asset, *Filename, Args);
}

void ConfigureWidget(
    UWidget* Widget,
    const FTigerStudioUMGLayerRecord& Layer,
    UCanvasPanel* Parent)
{
    Widget->SetRenderOpacity(static_cast<float>(Layer.Opacity));
    Widget->SetRenderTransformPivot(Layer.Anchor);
    Widget->SetRenderTransform(
        FWidgetTransform(
            FVector2D::ZeroVector,
            Layer.Scale,
            FVector2D::ZeroVector,
            static_cast<float>(Layer.RotationDegrees)));
    if (UCanvasPanelSlot* Slot = Parent->AddChildToCanvas(Widget))
    {
        Slot->SetPosition(Layer.Position);
        Slot->SetSize(Layer.Size);
        Slot->SetAlignment(Layer.Anchor);
        Slot->SetAutoSize(false);
    }
}
}

FTigerStudioUMGGenerationResult
UTigerStudioUMGImportSubsystem::GenerateDocumentFile(
    const FString& DocumentPath,
    const FString& DestinationRoot) const
{
    FTigerStudioUMGGenerationResult Result;
    const FTigerStudioUMGPreflightResult Preflight =
        PreflightDocumentFile(DocumentPath);
    if (!Preflight.bSuccess)
    {
        Result.Message = Preflight.Message;
        Result.Errors.Add(Preflight.Message);
        return Result;
    }

    FTigerStudioUMGDocumentRecord Document = Preflight.Document;
    const FString DocumentDirectory = FPaths::GetPath(DocumentPath);
    const FString SafeDocumentId = SafeObjectName(Document.DocumentId);
    const FString GeneratedRoot = FString::Printf(
        TEXT("%s/%s"),
        *DestinationRoot,
        *SafeDocumentId);

    IAssetTools& AssetTools =
        FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();
    TMap<FString, FSoftObjectPath> ResourcePaths;
    TArray<UAssetImportTask*> ImportTasks;
    TArray<FString> ImportResourceIds;

    for (const FTigerStudioUMGResourceRecord& Resource : Document.Resources)
    {
        const FString SourcePath = FPaths::IsRelative(Resource.SourcePath)
            ? FPaths::ConvertRelativePathToFull(DocumentDirectory, Resource.SourcePath)
            : Resource.SourcePath;
        const FString Kind = Resource.Kind.ToLower();
        const FString Folder = Kind == TEXT("sound")
            ? TEXT("Audio")
            : Kind == TEXT("font") ? TEXT("Fonts") : TEXT("Textures");
        UAssetImportTask* Task = NewObject<UAssetImportTask>();
        Task->Filename = SourcePath;
        Task->DestinationPath = GeneratedRoot / Folder;
        Task->DestinationName = SafeObjectName(Resource.DestinationName);
        Task->bAutomated = true;
        Task->bReplaceExisting = true;
        Task->bReplaceExistingSettings = false;
        Task->bSave = true;
        ImportTasks.Add(Task);
        ImportResourceIds.Add(Resource.Id);
    }

    if (!ImportTasks.IsEmpty())
    {
        AssetTools.ImportAssetTasks(ImportTasks);
        for (int32 Index = 0; Index < ImportTasks.Num(); ++Index)
        {
            UAssetImportTask* Task = ImportTasks[Index];
            if (!Task || Task->ImportedObjectPaths.IsEmpty())
            {
                Result.Errors.Add(FString::Printf(
                    TEXT("Failed to import resource: %s"),
                    *ImportResourceIds[Index]));
                continue;
            }
            const FString ObjectPath = Task->ImportedObjectPaths[0];
            ResourcePaths.Add(
                ImportResourceIds[Index],
                FSoftObjectPath(ObjectPath));
            Result.ImportedAssetPaths.Add(ObjectPath);
            if (UTexture2D* Texture = Cast<UTexture2D>(
                    FSoftObjectPath(ObjectPath).TryLoad()))
            {
                Texture->Modify();
                Texture->LODGroup = TEXTUREGROUP_UI;
                Texture->NeverStream = true;
                Texture->SRGB = true;
                Texture->MarkPackageDirty();
                SaveAssetPackage(Texture);
            }
        }
    }

    if (!Result.Errors.IsEmpty())
    {
        Result.Message = TEXT("One or more Tiger UMG resources failed to import.");
        return Result;
    }

    const FString WidgetPath = GeneratedRoot / TEXT("Widgets");
    const FString WidgetName = TEXT("WBP_TS_") + SafeDocumentId;
    const FString WidgetObjectPath = FString::Printf(
        TEXT("%s/%s.%s"),
        *WidgetPath,
        *WidgetName,
        *WidgetName);
    UWidgetBlueprint* Blueprint =
        LoadObject<UWidgetBlueprint>(nullptr, *WidgetObjectPath);
    if (!Blueprint)
    {
        UWidgetBlueprintFactory* Factory = NewObject<UWidgetBlueprintFactory>();
        Factory->ParentClass = UTigerStudioGeneratedWidget::StaticClass();
        Blueprint = Cast<UWidgetBlueprint>(
            AssetTools.CreateAsset(
                WidgetName,
                WidgetPath,
                UWidgetBlueprint::StaticClass(),
                Factory));
    }
    if (!Blueprint || !Blueprint->WidgetTree)
    {
        Result.Message = TEXT("Could not create the Tiger Widget Blueprint.");
        Result.Errors.Add(Result.Message);
        return Result;
    }

    Blueprint->Modify();
    Blueprint->WidgetTree->Modify();
    UCanvasPanel* RootCanvas = Cast<UCanvasPanel>(Blueprint->WidgetTree->RootWidget);
    if (!RootCanvas)
    {
        if (Blueprint->WidgetTree->RootWidget)
        {
            Result.Message =
                TEXT("Existing Widget Blueprint root is not a CanvasPanel.");
            Result.Errors.Add(Result.Message);
            return Result;
        }
        RootCanvas = Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
            UCanvasPanel::StaticClass(),
            TEXT("TigerCanvas"));
        Blueprint->WidgetTree->RootWidget = RootCanvas;
    }

    if (UWidget* ExistingGenerated =
            Blueprint->WidgetTree->FindWidget(TEXT("TigerGeneratedRoot")))
    {
        if (UPanelWidget* Parent = ExistingGenerated->GetParent())
        {
            Parent->RemoveChild(ExistingGenerated);
        }
        Blueprint->WidgetTree->RemoveWidget(ExistingGenerated);
    }

    UCanvasPanel* GeneratedPanel =
        Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
            UCanvasPanel::StaticClass(),
            TEXT("TigerGeneratedRoot"));
    UCanvasPanelSlot* GeneratedSlot = RootCanvas->AddChildToCanvas(GeneratedPanel);
    GeneratedSlot->SetAnchors(FAnchors(0.0, 0.0, 1.0, 1.0));
    GeneratedSlot->SetOffsets(FMargin(0.0));

    TMap<FString, UCanvasPanel*> ParentPanels;
    ParentPanels.Add(TEXT(""), GeneratedPanel);
    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        if (Layer.Disposition != ETigerStudioUMGDisposition::Native)
        {
            continue;
        }
        if (Layer.Kind == ETigerStudioUMGLayerKind::Group)
        {
            UCanvasPanel* Parent = ParentPanels.FindRef(Layer.ParentId);
            Parent = Parent ? Parent : GeneratedPanel;
            UCanvasPanel* Group =
                Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(
                    UCanvasPanel::StaticClass(),
                    FName(*Layer.Id));
            ConfigureWidget(Group, Layer, Parent);
            ParentPanels.Add(Layer.Id, Group);
            ++Result.GeneratedWidgetCount;
        }
    }

    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        if (Layer.Disposition != ETigerStudioUMGDisposition::Native
            || Layer.Kind == ETigerStudioUMGLayerKind::Group)
        {
            continue;
        }
        UCanvasPanel* Parent = ParentPanels.FindRef(Layer.ParentId);
        Parent = Parent ? Parent : GeneratedPanel;
        const TSharedPtr<FJsonObject> Payload = ParsePayload(Layer.PayloadJson);
        UWidget* Widget = nullptr;
        UImage* Image = nullptr;
        UTextBlock* Text = nullptr;

        if (Layer.Kind == ETigerStudioUMGLayerKind::Text)
        {
            Text = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(
                UTextBlock::StaticClass(),
                FName(*Layer.Id));
            Text->SetText(FText::FromString(
                Payload ? Payload->GetStringField(TEXT("text")) : Layer.Name));
            Text->SetColorAndOpacity(PayloadColor(
                Payload,
                TEXT("fill"),
                FLinearColor::White));
            FSlateFontInfo Font = Text->GetFont();
            double FontSize = 48.0;
            if (Payload)
            {
                Payload->TryGetNumberField(TEXT("font_size"), FontSize);
            }
            Font.Size = FMath::Max(1, FMath::RoundToInt(FontSize));
            Text->SetFont(Font);
            Widget = Text;
        }
        else if (Layer.Kind == ETigerStudioUMGLayerKind::Button)
        {
            UTigerStudioButton* Button =
                Blueprint->WidgetTree->ConstructWidget<UTigerStudioButton>(
                    UTigerStudioButton::StaticClass(),
                    FName(*Layer.Id));
            Button->TigerComponentId = Layer.Id;
            UTexture2D* ButtonTexture = nullptr;
            if (const FSoftObjectPath* AssetPath = ResourcePaths.Find(Layer.AssetId))
            {
                ButtonTexture = Cast<UTexture2D>(AssetPath->TryLoad());
            }
            if (ButtonTexture)
            {
                UImage* ButtonImage =
                    Blueprint->WidgetTree->ConstructWidget<UImage>(
                        UImage::StaticClass(),
                        FName(*(Layer.Id + TEXT("_Image"))));
                ButtonImage->SetBrushFromTexture(ButtonTexture, true);
                Button->AddChild(ButtonImage);
            }
            else
            {
                UTextBlock* Label =
                    Blueprint->WidgetTree->ConstructWidget<UTextBlock>(
                        UTextBlock::StaticClass(),
                        FName(*(Layer.Id + TEXT("_Label"))));
                FString LabelText = Layer.Name;
                if (Payload)
                {
                    Payload->TryGetStringField(TEXT("text"), LabelText);
                }
                Label->SetText(FText::FromString(LabelText));
                Button->AddChild(Label);
            }
            Widget = Button;
        }
        else
        {
            Image = Blueprint->WidgetTree->ConstructWidget<UImage>(
                UImage::StaticClass(),
                FName(*Layer.Id));
            if (const FSoftObjectPath* AssetPath = ResourcePaths.Find(Layer.AssetId))
            {
                if (UTexture2D* Texture = Cast<UTexture2D>(AssetPath->TryLoad()))
                {
                    Image->SetBrushFromTexture(Texture, true);
                }
            }
            Image->SetColorAndOpacity(PayloadColor(
                Payload,
                TEXT("fill"),
                FLinearColor::White));
            Widget = Image;
        }

        if (Widget)
        {
            ConfigureWidget(Widget, Layer, Parent);
            ++Result.GeneratedWidgetCount;
        }
    }

    Blueprint->Animations.RemoveAll(
        [](const UWidgetAnimation* Animation)
        {
            return Animation
                && Animation->GetName().StartsWith(TEXT("Tiger_"));
        });
    TMap<FString, TArray<const FTigerStudioUMGAnimationTrackRecord*>> AnimationGroups;
    for (const FTigerStudioUMGAnimationTrackRecord& Track : Document.Animations)
    {
        AnimationGroups.FindOrAdd(
            Track.AnimationName.IsEmpty() ? TEXT("TigerTimeline") : Track.AnimationName)
            .Add(&Track);
    }
    for (const TPair<FString, TArray<const FTigerStudioUMGAnimationTrackRecord*>>& Group :
         AnimationGroups)
    {
        const FString AnimationName = TEXT("Tiger_") + SafeObjectName(Group.Key);
        UWidgetAnimation* Animation = NewObject<UWidgetAnimation>(
            Blueprint,
            FName(*AnimationName),
            RF_Transactional);
        Animation->SetDisplayLabel(Group.Key);
        Animation->MovieScene = NewObject<UMovieScene>(
            Animation,
            FName(*AnimationName),
            RF_Transactional);
        Animation->MovieScene->SetDisplayRate(
            FFrameRate(FMath::Max(1, FMath::RoundToInt(Document.FrameRate)), 1));
        Animation->MovieScene->SetTickResolutionDirectly(FFrameRate(1000, 1));
        Animation->MovieScene->SetPlaybackRange(
            TRange<FFrameNumber>(
                FFrameNumber(0),
                FFrameNumber(Document.DurationMilliseconds + 1)));

        TMap<FString, TArray<const FTigerStudioUMGAnimationTrackRecord*>> LayerTracks;
        for (const FTigerStudioUMGAnimationTrackRecord* Track : Group.Value)
        {
            LayerTracks.FindOrAdd(Track->LayerId).Add(Track);
        }
        for (const TPair<FString, TArray<const FTigerStudioUMGAnimationTrackRecord*>>&
             LayerGroup : LayerTracks)
        {
            const FGuid BindingId = Animation->MovieScene->AddPossessable(
                LayerGroup.Key,
                UWidget::StaticClass());
            FWidgetAnimationBinding Binding;
            Binding.WidgetName = FName(*LayerGroup.Key);
            Binding.AnimationGuid = BindingId;
            Animation->AnimationBindings.Add(Binding);

            UMovieScene2DTransformSection* TransformSection = nullptr;
            UMovieSceneFloatSection* OpacitySection = nullptr;
            for (const FTigerStudioUMGAnimationTrackRecord* Track : LayerGroup.Value)
            {
                const FString Property = Track->Property.ToLower();
                if (Property == TEXT("opacity"))
                {
                    if (!OpacitySection)
                    {
                        UMovieSceneFloatTrack* FloatTrack =
                            Animation->MovieScene->AddTrack<UMovieSceneFloatTrack>(
                                BindingId);
                        FloatTrack->SetPropertyNameAndPath(
                            TEXT("RenderOpacity"),
                            TEXT("RenderOpacity"));
                        OpacitySection = Cast<UMovieSceneFloatSection>(
                            FloatTrack->CreateNewSection());
                        OpacitySection->SetRange(
                            Animation->MovieScene->GetPlaybackRange());
                        FloatTrack->AddSection(*OpacitySection);
                    }
                    for (const FTigerStudioUMGKeyframeRecord& Key : Track->Keyframes)
                    {
                        AddKey(
                            OpacitySection->GetChannel(),
                            Key,
                            static_cast<float>(Key.Value.X));
                    }
                    continue;
                }
                if (!TransformSection)
                {
                    UMovieScene2DTransformTrack* TransformTrack =
                        Animation->MovieScene->AddTrack<UMovieScene2DTransformTrack>(
                            BindingId);
                    TransformTrack->SetPropertyNameAndPath(
                        TEXT("RenderTransform"),
                        TEXT("RenderTransform"));
                    TransformSection = Cast<UMovieScene2DTransformSection>(
                        TransformTrack->CreateNewSection());
                    TransformSection->SetMask(
                        FMovieScene2DTransformMask(
                            EMovieScene2DTransformChannel::AllTransform));
                    TransformSection->SetRange(
                        Animation->MovieScene->GetPlaybackRange());
                    TransformTrack->AddSection(*TransformSection);
                }
                for (const FTigerStudioUMGKeyframeRecord& Key : Track->Keyframes)
                {
                    if (Property == TEXT("position"))
                    {
                        AddKey(
                            TransformSection->Translation[0],
                            Key,
                            static_cast<float>(Key.Value.X));
                        AddKey(
                            TransformSection->Translation[1],
                            Key,
                            static_cast<float>(Key.Value.Y));
                    }
                    else if (Property == TEXT("scale"))
                    {
                        AddKey(
                            TransformSection->Scale[0],
                            Key,
                            static_cast<float>(Key.Value.X));
                        AddKey(
                            TransformSection->Scale[1],
                            Key,
                            static_cast<float>(Key.Value.Y));
                    }
                    else if (Property == TEXT("rotation"))
                    {
                        AddKey(
                            TransformSection->Rotation,
                            Key,
                            static_cast<float>(Key.Value.X));
                    }
                }
            }
        }
        Blueprint->Animations.Add(Animation);
        ++Result.GeneratedAnimationCount;
    }

    for (FTigerStudioUMGInteractionRecord& Interaction : Document.Interactions)
    {
        for (FTigerStudioUMGActionRecord& Action : Interaction.Actions)
        {
            if (const FSoftObjectPath* ResourcePath =
                    ResourcePaths.Find(Action.ResourceId))
            {
                Action.ResourcePath = *ResourcePath;
            }
            if (Action.Type.Equals(TEXT("play_animation"), ESearchCase::IgnoreCase)
                && !Action.Name.StartsWith(TEXT("Tiger_")))
            {
                Action.Name = TEXT("Tiger_") + SafeObjectName(Action.Name);
            }
        }
    }

    FAssetRegistryModule::AssetCreated(Blueprint);
    Blueprint->MarkPackageDirty();
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    if (Blueprint->Status == BS_Error || !Blueprint->GeneratedClass)
    {
        Result.Message = TEXT("Generated Widget Blueprint did not compile.");
        Result.Errors.Add(Result.Message);
        return Result;
    }
    if (UTigerStudioGeneratedWidget* Defaults =
            Cast<UTigerStudioGeneratedWidget>(
                Blueprint->GeneratedClass->GetDefaultObject()))
    {
        Defaults->TigerSourceProvider = Document.Provider;
        Defaults->TigerSourceDocumentId = Document.DocumentId;
        Defaults->TigerSourceRevision = Document.Revision;
        Defaults->TigerInteractions = Document.Interactions;
    }
    Blueprint->MarkPackageDirty();
    if (!SaveAssetPackage(Blueprint))
    {
        Result.Message = TEXT("Generated Widget Blueprint could not be saved.");
        Result.Errors.Add(Result.Message);
        return Result;
    }

    Result.bSuccess = true;
    Result.GeneratedAssetPath = WidgetObjectPath;
    Result.Message = FString::Printf(
        TEXT("Generated %d widgets and %d animations."),
        Result.GeneratedWidgetCount,
        Result.GeneratedAnimationCount);
    return Result;
}
