#include "TigerStudioUMGImportSubsystem.h"

#include "JsonObjectConverter.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

FTigerStudioUMGPreflightResult
UTigerStudioUMGImportSubsystem::PreflightDocumentFile(const FString& DocumentPath) const
{
    FTigerStudioUMGPreflightResult Result;
    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *DocumentPath))
    {
        Result.Message = FString::Printf(TEXT("Could not read Tiger UMG document: %s"), *DocumentPath);
        return Result;
    }

    FText FailureReason;
    if (!FJsonObjectConverter::JsonObjectStringToUStruct(
            JsonText,
            &Result.Document,
            0,
            0,
            true,
            &FailureReason))
    {
        Result.Message = FailureReason.ToString();
        return Result;
    }

    if (Result.Document.SchemaVersion != 4)
    {
        Result.Message = FString::Printf(
            TEXT("Unsupported Tiger UMG schema version: %d"),
            Result.Document.SchemaVersion);
        return Result;
    }
    if (Result.Document.Provider.IsEmpty() || Result.Document.DocumentId.IsEmpty())
    {
        Result.Message = TEXT("Provider and DocumentId are required.");
        return Result;
    }
    if (Result.Document.Width <= 0 || Result.Document.Height <= 0)
    {
        Result.Message = TEXT("Document dimensions must be positive.");
        return Result;
    }

    Result.ResourceCount = Result.Document.Resources.Num();
    Result.InteractionCount = Result.Document.Interactions.Num();
    TSet<FString> ResourceIds;
    const FString DocumentDirectory = FPaths::GetPath(DocumentPath);
    for (const FTigerStudioUMGResourceRecord& Resource : Result.Document.Resources)
    {
        if (Resource.Id.IsEmpty() || ResourceIds.Contains(Resource.Id))
        {
            Result.Message = TEXT("Resource IDs must be non-empty and unique.");
            return Result;
        }
        ResourceIds.Add(Resource.Id);
        const FString SourcePath = FPaths::IsRelative(Resource.SourcePath)
            ? FPaths::ConvertRelativePathToFull(DocumentDirectory, Resource.SourcePath)
            : Resource.SourcePath;
        if (!FPaths::FileExists(SourcePath))
        {
            Result.Message = FString::Printf(
                TEXT("Resource file is missing: %s"),
                *SourcePath);
            return Result;
        }
    }

    for (const FTigerStudioUMGLayerRecord& Layer : Result.Document.Layers)
    {
        switch (Layer.Disposition)
        {
        case ETigerStudioUMGDisposition::Native:
            ++Result.NativeLayerCount;
            break;
        case ETigerStudioUMGDisposition::Material:
            ++Result.MaterialLayerCount;
            break;
        case ETigerStudioUMGDisposition::Baked:
            ++Result.BakedLayerCount;
            break;
        case ETigerStudioUMGDisposition::Blocked:
            ++Result.BlockedLayerCount;
            if (Layer.BlockReasons.IsEmpty())
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":unsupported_layer"));
            }
            else
            {
                for (const FString& Reason : Layer.BlockReasons)
                {
                    Result.BlockReasons.Add(
                        Layer.Id + TEXT(":") + Reason);
                }
            }
            break;
        default:
            break;
        }
    }

    if (Result.BlockedLayerCount > 0)
    {
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by %d unsupported layer(s): %s"),
            Result.BlockedLayerCount,
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }

    Result.bSuccess = true;
    Result.Message = TEXT("Tiger UMG document is ready for native generation.");
    return Result;
}
