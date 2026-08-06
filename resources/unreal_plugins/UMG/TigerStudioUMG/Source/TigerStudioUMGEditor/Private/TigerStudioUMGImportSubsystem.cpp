#include "TigerStudioUMGImportSubsystem.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "JsonObjectConverter.h"
#include "Misc/Crc.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Policies/CondensedJsonPrintPolicy.h"

#include <initializer_list>

THIRD_PARTY_INCLUDES_START
#include <openssl/sha.h>
THIRD_PARTY_INCLUDES_END

namespace
{
constexpr const TCHAR* StaticVectorBakeSchema =
    TEXT("tigerstudio.umg.static_vector_bake.v2");
constexpr const TCHAR* StaticVectorBakeRenderer =
    TEXT("qt_svg_fill_geometry_v3");
constexpr const TCHAR* StaticVectorBakeGate =
    TEXT("figma_vector_geometry_requires_deterministic_bake");
constexpr int32 StaticVectorBakeMaxSubpaths = 256;
constexpr double StaticVectorBakeBoundsEpsilon = 0.0001;
constexpr const TCHAR* StaticAppearanceBakeSchema =
    TEXT("tigerstudio.umg.static_appearance_bake.v1");
constexpr const TCHAR* StaticAppearanceBakeKind =
    TEXT("static_figma_appearance_png");
constexpr const TCHAR* StaticAppearanceBakeGate =
    TEXT("figma_noise_effect_requires_ui_material_or_deterministic_bake");
constexpr int32 StaticAppearanceBakeSchemaVersion = 14;
constexpr const TCHAR* StaticTextureBakeSchema =
    TEXT("tigerstudio.umg.static_texture_bake.v1");
constexpr const TCHAR* StaticTextureBakeKind =
    TEXT("static_figma_texture_png");
constexpr const TCHAR* StaticTextureBakeGate =
    TEXT("figma_texture_effect_requires_ui_material_or_deterministic_bake");
constexpr int32 StaticTextureBakeSchemaVersion = 15;
constexpr int32 ButtonStyleSchemaVersion = 16;
constexpr const TCHAR* ButtonStyleSchema =
    TEXT("tigerstudio.umg.button_style.v1");
constexpr int32 LayerVisibilitySchemaVersion = 16;
constexpr int32 OverlayPanelSchemaVersion = 17;
constexpr int32 SpacingStrategySchemaVersion = 17;
constexpr int32 ComponentSchemaVersion = 18;
constexpr int32 DynamicRoundedCardSizeSchemaVersion = 19;
constexpr int32 StaticAppearanceBakeMaxDimension = 4096;
constexpr int64 StaticAppearanceBakeMaxPixels = 16 * 1024 * 1024;
constexpr int64 StaticAppearanceBakeMaxFileBytes = 128 * 1024 * 1024;
constexpr int64 StaticAppearanceBakeMaxMetadataBytes = 1024 * 1024;
constexpr double StaticAppearanceBakeBoundsEpsilon = 0.000001;

FString SafeResourceObjectName(const FString& Input)
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

FString ResourceFolder(const FString& Kind)
{
    return Kind.Equals(TEXT("sound"), ESearchCase::IgnoreCase)
        ? TEXT("Audio")
        : Kind.Equals(TEXT("font"), ESearchCase::IgnoreCase)
            ? TEXT("Fonts")
            : TEXT("Textures");
}

bool HashFileSha256(const FString& Path, FString& OutHash)
{
    TArray<uint8> Bytes;
    if (!FFileHelper::LoadFileToArray(Bytes, *Path))
    {
        return false;
    }
    uint8 Digest[SHA256_DIGEST_LENGTH];
    if (!SHA256(
            Bytes.GetData(),
            static_cast<size_t>(Bytes.Num()),
            Digest))
    {
        return false;
    }
    OutHash = BytesToHexLower(Digest, SHA256_DIGEST_LENGTH);
    return true;
}

bool HashBytesSha256(
    const void* Data,
    const int64 DataSize,
    FString& OutHash)
{
    if (!Data || DataSize < 0)
    {
        return false;
    }
    uint8 Digest[SHA256_DIGEST_LENGTH];
    if (!SHA256(
            static_cast<const uint8*>(Data),
            static_cast<size_t>(DataSize),
            Digest))
    {
        return false;
    }
    OutHash = BytesToHexLower(Digest, SHA256_DIGEST_LENGTH);
    return true;
}

bool HashUtf8Sha256(const FString& Value, FString& OutHash)
{
    FTCHARToUTF8 Utf8(*Value);
    if (Utf8.Length() < 0)
    {
        return false;
    }
    uint8 Digest[SHA256_DIGEST_LENGTH];
    if (!SHA256(
            reinterpret_cast<const uint8*>(Utf8.Get()),
            static_cast<size_t>(Utf8.Length()),
            Digest))
    {
        return false;
    }
    OutHash = BytesToHexLower(Digest, SHA256_DIGEST_LENGTH);
    return true;
}

FString JsonQuotedString(const FString& Value)
{
    FString Result;
    const TSharedRef<TJsonWriter<
        TCHAR,
        TCondensedJsonPrintPolicy<TCHAR>>> Writer =
        TJsonWriterFactory<
            TCHAR,
            TCondensedJsonPrintPolicy<TCHAR>>::Create(&Result);
    Writer->WriteValue(Value);
    Writer->Close();
    return Result;
}

FString PythonCanonicalFloat(const double Value)
{
    FString Result = FString::Printf(TEXT("%.9f"), Value);
    while (Result.EndsWith(TEXT("0")) && !Result.EndsWith(TEXT(".0")))
    {
        Result.LeftChopInline(1, EAllowShrinking::No);
    }
    return Result;
}

bool AppendCanonicalJson(
    const TSharedPtr<FJsonValue>& Value,
    const FString& FieldName,
    FString& Out)
{
    if (!Value)
    {
        return false;
    }
    switch (Value->Type)
    {
    case EJson::Null:
        Out += TEXT("null");
        return true;
    case EJson::String:
        Out += JsonQuotedString(Value->AsString());
        return true;
    case EJson::Boolean:
        Out += Value->AsBool() ? TEXT("true") : TEXT("false");
        return true;
    case EJson::Number:
    {
        const double Number = Value->AsNumber();
        if (!FMath::IsFinite(Number))
        {
            return false;
        }
        if (FieldName == TEXT("width")
            || FieldName == TEXT("height")
            || FieldName == TEXT("x")
            || FieldName == TEXT("y")
            || FieldName == TEXT("logical_bounds_epsilon"))
        {
            Out += PythonCanonicalFloat(Number);
            return true;
        }
        if (!FMath::IsNearlyEqual(
                Number,
                FMath::RoundToDouble(Number),
                0.000001))
        {
            return false;
        }
        Out += FString::Printf(TEXT("%lld"), static_cast<int64>(Number));
        return true;
    }
    case EJson::Array:
    {
        Out += TEXT("[");
        const TArray<TSharedPtr<FJsonValue>>& Values = Value->AsArray();
        for (int32 Index = 0; Index < Values.Num(); ++Index)
        {
            if (Index > 0)
            {
                Out += TEXT(",");
            }
            if (!AppendCanonicalJson(Values[Index], FieldName, Out))
            {
                return false;
            }
        }
        Out += TEXT("]");
        return true;
    }
    case EJson::Object:
    {
        const TSharedPtr<FJsonObject> Object = Value->AsObject();
        if (!Object)
        {
            return false;
        }
        TArray<FString> Keys;
        Keys.Reserve(Object->Values.Num());
        for (const auto& Pair : Object->Values)
        {
            Keys.Emplace(Pair.Key.Len(), *Pair.Key);
        }
        Keys.Sort();
        Out += TEXT("{");
        for (int32 Index = 0; Index < Keys.Num(); ++Index)
        {
            if (Index > 0)
            {
                Out += TEXT(",");
            }
            Out += JsonQuotedString(Keys[Index]) + TEXT(":");
            const TSharedPtr<FJsonValue> Child =
                Object->TryGetField(Keys[Index]);
            if (!AppendCanonicalJson(Child, Keys[Index], Out))
            {
                return false;
            }
        }
        Out += TEXT("}");
        return true;
    }
    default:
        return false;
    }
}

uint32 ReadPngUInt32(const uint8* Bytes)
{
    return (static_cast<uint32>(Bytes[0]) << 24)
        | (static_cast<uint32>(Bytes[1]) << 16)
        | (static_cast<uint32>(Bytes[2]) << 8)
        | static_cast<uint32>(Bytes[3]);
}

bool ValidateStaticVectorPng(
    const FString& Path,
    const int32 ExpectedWidth,
    const int32 ExpectedHeight)
{
    TArray<uint8> Bytes;
    static const uint8 Signature[] = {
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a};
    if (!FFileHelper::LoadFileToArray(Bytes, *Path)
        || Bytes.Num() < 33
        || FMemory::Memcmp(Bytes.GetData(), Signature, 8) != 0)
    {
        return false;
    }
    bool bValidIHDR = false;
    bool bValidSRGB = false;
    int64 Offset = 8;
    while (Offset + 12 <= Bytes.Num())
    {
        const uint32 Length = ReadPngUInt32(Bytes.GetData() + Offset);
        if (Length > static_cast<uint32>(Bytes.Num())
            || Offset + 12 + static_cast<int64>(Length) > Bytes.Num())
        {
            return false;
        }
        const uint8* Type = Bytes.GetData() + Offset + 4;
        const uint8* Data = Bytes.GetData() + Offset + 8;
        if (FMemory::Memcmp(Type, "IHDR", 4) == 0)
        {
            bValidIHDR = Length == 13
                && ReadPngUInt32(Data) == static_cast<uint32>(ExpectedWidth)
                && ReadPngUInt32(Data + 4)
                    == static_cast<uint32>(ExpectedHeight)
                && Data[8] == 8
                && Data[9] == 6;
        }
        else if (FMemory::Memcmp(Type, "sRGB", 4) == 0)
        {
            bValidSRGB = Length == 1 && Data[0] == 0;
        }
        Offset += 12 + static_cast<int64>(Length);
    }
    return bValidIHDR && bValidSRGB;
}

bool ValidateStaticAppearancePng(
    const FString& Path,
    const int32 ExpectedWidth,
    const int32 ExpectedHeight,
    const FString& ExpectedPixelHash)
{
    TArray<uint8> Bytes;
    static const uint8 Signature[] = {
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a};
    if (!FFileHelper::LoadFileToArray(Bytes, *Path)
        || Bytes.Num() < 57
        || Bytes.Num() > StaticAppearanceBakeMaxFileBytes
        || FMemory::Memcmp(Bytes.GetData(), Signature, 8) != 0
        || ExpectedWidth <= 0
        || ExpectedHeight <= 0
        || ExpectedWidth > StaticAppearanceBakeMaxDimension
        || ExpectedHeight > StaticAppearanceBakeMaxDimension
        || static_cast<int64>(ExpectedWidth) * ExpectedHeight
            > StaticAppearanceBakeMaxPixels)
    {
        return false;
    }

    bool bSawIHDR = false;
    bool bSawSRGB = false;
    bool bSawIDAT = false;
    bool bFinishedIDAT = false;
    bool bSawIEND = false;
    int64 MetadataBytes = 0;
    int64 Offset = 8;
    while (Offset < Bytes.Num())
    {
        if (Offset + 12 > Bytes.Num())
        {
            return false;
        }
        const uint32 Length = ReadPngUInt32(Bytes.GetData() + Offset);
        const int64 ChunkEnd = Offset + 12 + static_cast<int64>(Length);
        if (Length > static_cast<uint32>(StaticAppearanceBakeMaxFileBytes)
            || ChunkEnd > Bytes.Num())
        {
            return false;
        }
        const uint8* Type = Bytes.GetData() + Offset + 4;
        const uint8* Data = Bytes.GetData() + Offset + 8;
        const uint32 StoredCrc = ReadPngUInt32(
            Bytes.GetData() + Offset + 8 + Length);
        if (FCrc::MemCrc32(
                Type,
                static_cast<int32>(Length + 4)) != StoredCrc)
        {
            return false;
        }

        const bool bIHDR = FMemory::Memcmp(Type, "IHDR", 4) == 0;
        const bool bSRGB = FMemory::Memcmp(Type, "sRGB", 4) == 0;
        const bool bIDAT = FMemory::Memcmp(Type, "IDAT", 4) == 0;
        const bool bIEND = FMemory::Memcmp(Type, "IEND", 4) == 0;
        const bool bForbiddenColorMetadata =
            FMemory::Memcmp(Type, "iCCP", 4) == 0
            || FMemory::Memcmp(Type, "gAMA", 4) == 0
            || FMemory::Memcmp(Type, "cHRM", 4) == 0
            || FMemory::Memcmp(Type, "PLTE", 4) == 0;
        const bool bUnknownCritical = (Type[0] & 0x20) == 0
            && !bIHDR
            && !bIDAT
            && !bIEND;
        if (bForbiddenColorMetadata || bUnknownCritical || bSawIEND)
        {
            return false;
        }

        if (bIHDR)
        {
            if (bSawIHDR
                || Offset != 8
                || Length != 13
                || ReadPngUInt32(Data)
                    != static_cast<uint32>(ExpectedWidth)
                || ReadPngUInt32(Data + 4)
                    != static_cast<uint32>(ExpectedHeight)
                || Data[8] != 8
                || Data[9] != 6
                || Data[10] != 0
                || Data[11] != 0
                || Data[12] != 0)
            {
                return false;
            }
            bSawIHDR = true;
        }
        else if (bSRGB)
        {
            if (!bSawIHDR
                || bSawSRGB
                || bSawIDAT
                || Length != 1
                || Data[0] != 0)
            {
                return false;
            }
            bSawSRGB = true;
        }
        else if (bIDAT)
        {
            if (!bSawIHDR || !bSawSRGB || bFinishedIDAT || Length == 0)
            {
                return false;
            }
            bSawIDAT = true;
        }
        else if (bIEND)
        {
            if (!bSawIDAT || Length != 0 || ChunkEnd != Bytes.Num())
            {
                return false;
            }
            bFinishedIDAT = true;
            bSawIEND = true;
        }
        else
        {
            if (!bSawIHDR || bSawIDAT)
            {
                bFinishedIDAT = bSawIDAT;
            }
            MetadataBytes += Length;
            if (MetadataBytes > StaticAppearanceBakeMaxMetadataBytes)
            {
                return false;
            }
        }
        Offset = ChunkEnd;
    }
    if (!bSawIHDR || !bSawSRGB || !bSawIDAT || !bSawIEND)
    {
        return false;
    }

    IImageWrapperModule& ImageWrapperModule =
        FModuleManager::LoadModuleChecked<IImageWrapperModule>(
            TEXT("ImageWrapper"));
    const TSharedPtr<IImageWrapper> Wrapper =
        ImageWrapperModule.CreateImageWrapper(EImageFormat::PNG, *Path);
    if (!Wrapper
        || !Wrapper->SetCompressed(Bytes.GetData(), Bytes.Num())
        || Wrapper->GetWidth() != ExpectedWidth
        || Wrapper->GetHeight() != ExpectedHeight
        || Wrapper->GetBitDepth() != 8)
    {
        return false;
    }
    TArray64<uint8> RawRgba;
    const int64 ExpectedByteCount =
        static_cast<int64>(ExpectedWidth) * ExpectedHeight * 4;
    FString ActualPixelHash;
    return Wrapper->GetRaw(ERGBFormat::RGBA, 8, RawRgba)
        && RawRgba.Num() == ExpectedByteCount
        && HashBytesSha256(
            RawRgba.GetData(),
            RawRgba.Num(),
            ActualPixelHash)
        && ActualPixelHash.Equals(
            ExpectedPixelHash,
            ESearchCase::IgnoreCase);
}

bool IsSafeRelativeArtifactPath(
    const FString& Value,
    const FString& ExpectedExtension)
{
    if (Value.IsEmpty()
        || Value.Contains(TEXT("\\"))
        || Value.StartsWith(TEXT("/"))
        || Value.Contains(TEXT("//"))
        || (Value.Len() >= 2
            && FChar::IsAlpha(Value[0])
            && Value[1] == TEXT(':'))
        || !FPaths::IsRelative(Value)
        || !FPaths::GetExtension(Value).Equals(
            ExpectedExtension,
            ESearchCase::IgnoreCase))
    {
        return false;
    }
    TArray<FString> Parts;
    Value.ParseIntoArray(Parts, TEXT("/"), false);
    return !Parts.IsEmpty()
        && !Parts.ContainsByPredicate([](const FString& Part)
        {
            return Part.IsEmpty()
                || Part == TEXT(".")
                || Part == TEXT("..");
        });
}

TSharedPtr<FJsonObject> Vector2DJson(const double X, const double Y)
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("X"), X);
    Result->SetNumberField(TEXT("Y"), Y);
    return Result;
}

TSharedPtr<FJsonObject> Vector4Json(
    const double X,
    const double Y,
    const double Z,
    const double W)
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("X"), X);
    Result->SetNumberField(TEXT("Y"), Y);
    Result->SetNumberField(TEXT("Z"), Z);
    Result->SetNumberField(TEXT("W"), W);
    return Result;
}

TSharedPtr<FJsonObject> MarginJson(
    const double Left,
    const double Top,
    const double Right,
    const double Bottom)
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("Left"), Left);
    Result->SetNumberField(TEXT("Top"), Top);
    Result->SetNumberField(TEXT("Right"), Right);
    Result->SetNumberField(TEXT("Bottom"), Bottom);
    return Result;
}

void AddV5DefaultsToV4Layers(const TSharedPtr<FJsonObject>& DocumentObject)
{
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        if (!Layer)
        {
            continue;
        }

        if (!Layer->HasField(TEXT("CanvasSlot")))
        {
            TSharedPtr<FJsonObject> CanvasSlot = MakeShared<FJsonObject>();
            CanvasSlot->SetObjectField(
                TEXT("AnchorMinimum"),
                Vector2DJson(0.0, 0.0));
            CanvasSlot->SetObjectField(
                TEXT("AnchorMaximum"),
                Vector2DJson(0.0, 0.0));
            TSharedPtr<FJsonObject> Offsets = MakeShared<FJsonObject>();
            Offsets->SetNumberField(TEXT("Left"), 0.0);
            Offsets->SetNumberField(TEXT("Top"), 0.0);
            Offsets->SetNumberField(TEXT("Right"), 100.0);
            Offsets->SetNumberField(TEXT("Bottom"), 100.0);
            CanvasSlot->SetObjectField(TEXT("Offsets"), Offsets);
            CanvasSlot->SetObjectField(
                TEXT("Alignment"),
                Vector2DJson(0.5, 0.5));
            Layer->SetObjectField(TEXT("CanvasSlot"), CanvasSlot);
        }

        if (!Layer->HasField(TEXT("RenderTransformPivot")))
        {
            double PivotX = 0.5;
            double PivotY = 0.5;
            const TSharedPtr<FJsonObject>* LegacyAnchor = nullptr;
            if (Layer->TryGetObjectField(TEXT("Anchor"), LegacyAnchor)
                && LegacyAnchor
                && LegacyAnchor->IsValid())
            {
                (*LegacyAnchor)->TryGetNumberField(TEXT("X"), PivotX);
                (*LegacyAnchor)->TryGetNumberField(TEXT("Y"), PivotY);
            }
            Layer->SetObjectField(
                TEXT("RenderTransformPivot"),
                Vector2DJson(PivotX, PivotY));
        }
    }
}

void AddLegacyLayerDefaults(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer = LayerValue
            ? LayerValue->AsObject()
            : nullptr;
        if (!Layer)
        {
            continue;
        }
        if (SchemaVersion < 6 && !Layer->HasField(TEXT("Material")))
        {
            Layer->SetObjectField(
                TEXT("Material"),
                MakeShared<FJsonObject>());
        }
        if (SchemaVersion < 7)
        {
            if (!Layer->HasField(TEXT("PanelKind")))
            {
                Layer->SetStringField(TEXT("PanelKind"), TEXT("None"));
            }
            if (!Layer->HasField(TEXT("FlowSlot")))
            {
                TSharedPtr<FJsonObject> FlowSlot = MakeShared<FJsonObject>();
                FlowSlot->SetObjectField(
                    TEXT("Padding"),
                    MarginJson(0.0, 0.0, 0.0, 0.0));
                FlowSlot->SetStringField(
                    TEXT("HorizontalAlignment"),
                    TEXT("Fill"));
                FlowSlot->SetStringField(
                    TEXT("VerticalAlignment"),
                    TEXT("Fill"));
                FlowSlot->SetStringField(TEXT("SizeRule"), TEXT("Auto"));
                FlowSlot->SetNumberField(TEXT("FillCoefficient"), 1.0);
                Layer->SetObjectField(TEXT("FlowSlot"), FlowSlot);
            }
        }
        if (SchemaVersion < 10)
        {
            if (!Layer->HasField(TEXT("ScrollOverflow")))
            {
                Layer->SetStringField(TEXT("ScrollOverflow"), TEXT("None"));
            }
            if (!Layer->HasField(TEXT("ScrollPosition")))
            {
                Layer->SetStringField(TEXT("ScrollPosition"), TEXT("Scroll"));
            }
        }
        if (SchemaVersion < LayerVisibilitySchemaVersion
            && !Layer->HasField(TEXT("Visibility")))
        {
            Layer->SetStringField(TEXT("Visibility"), TEXT("Visible"));
        }
        if (SchemaVersion < 11 && !Layer->HasField(TEXT("ImageFill")))
        {
            Layer->SetObjectField(
                TEXT("ImageFill"),
                MakeShared<FJsonObject>());
        }
        if (SchemaVersion < 12 && !Layer->HasField(TEXT("Flipbook")))
        {
            Layer->SetObjectField(
                TEXT("Flipbook"),
                MakeShared<FJsonObject>());
        }
        if (SchemaVersion < ButtonStyleSchemaVersion
            && !Layer->HasField(TEXT("ButtonStyle")))
        {
            Layer->SetObjectField(
                TEXT("ButtonStyle"),
                MakeShared<FJsonObject>());
        }
        if (SchemaVersion < SpacingStrategySchemaVersion)
        {
            if (!Layer->HasField(TEXT("SpacingStrategy")))
            {
                Layer->SetStringField(
                    TEXT("SpacingStrategy"),
                    TEXT("Padding"));
            }
            if (!Layer->HasField(TEXT("SpacerSizeRule")))
            {
                Layer->SetStringField(
                    TEXT("SpacerSizeRule"),
                    TEXT("Auto"));
            }
            if (!Layer->HasField(TEXT("SpacerFillCoefficient")))
            {
                Layer->SetNumberField(
                    TEXT("SpacerFillCoefficient"),
                    1.0);
            }
        }
    }
}

void AddLegacyComponentDocumentDefaults(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    if (!DocumentObject || SchemaVersion >= ComponentSchemaVersion)
    {
        return;
    }

    // Components and ComponentInstances became required provider fields in
    // schema 18.  The strict USTRUCT reader still sees those newer members
    // when it opens a valid schema 4-17 document, so materialize only the
    // legacy empty defaults after raw validation and before deserialization.
    // A schema-18 document remains strict and must serialize both arrays.
    if (!DocumentObject->HasField(TEXT("Components")))
    {
        DocumentObject->SetArrayField(
            TEXT("Components"),
            TArray<TSharedPtr<FJsonValue>>());
    }
    if (!DocumentObject->HasField(TEXT("ComponentInstances")))
    {
        DocumentObject->SetArrayField(
            TEXT("ComponentInstances"),
            TArray<TSharedPtr<FJsonValue>>());
    }
}

TSharedPtr<FJsonObject> DefaultStrokeJson()
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("Width"), 0.0);
    Result->SetStringField(TEXT("Alignment"), TEXT("Inside"));
    Result->SetStringField(TEXT("Color"), TEXT("#00000000"));
    return Result;
}

TSharedPtr<FJsonObject> DefaultShadowJson()
{
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetBoolField(TEXT("Enabled"), false);
    Result->SetStringField(TEXT("Color"), TEXT("#00000000"));
    Result->SetObjectField(TEXT("Offset"), Vector2DJson(0.0, 0.0));
    Result->SetNumberField(TEXT("Blur"), 0.0);
    Result->SetNumberField(TEXT("Spread"), 0.0);
    return Result;
}

void AddV2DefaultsToLegacyMaterials(
    const TSharedPtr<FJsonObject>& DocumentObject)
{
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer = LayerValue
            ? LayerValue->AsObject()
            : nullptr;
        const TSharedPtr<FJsonObject>* MaterialField = nullptr;
        if (!Layer
            || !Layer->TryGetObjectField(TEXT("Material"), MaterialField)
            || !MaterialField
            || !MaterialField->IsValid())
        {
            continue;
        }
        const TSharedPtr<FJsonObject> Material = *MaterialField;
        FString MaterialSchema;
        if (!Material->TryGetStringField(TEXT("Schema"), MaterialSchema)
            || MaterialSchema != TEXT("tigerstudio.umg.ui_material.v1"))
        {
            continue;
        }

        if (!Material->HasField(TEXT("Size")))
        {
            Material->SetObjectField(TEXT("Size"), Vector2DJson(100.0, 100.0));
        }
        if (!Material->HasField(TEXT("FillKind")))
        {
            Material->SetStringField(TEXT("FillKind"), TEXT("Solid"));
        }
        if (!Material->HasField(TEXT("FillColor")))
        {
            Material->SetStringField(TEXT("FillColor"), TEXT("#FFFFFFFF"));
        }
        if (!Material->HasField(TEXT("CornerRadii")))
        {
            Material->SetObjectField(
                TEXT("CornerRadii"),
                Vector4Json(0.0, 0.0, 0.0, 0.0));
        }
        if (!Material->HasField(TEXT("CornerSmoothing")))
        {
            Material->SetNumberField(TEXT("CornerSmoothing"), 0.0);
        }
        if (!Material->HasField(TEXT("Stroke")))
        {
            Material->SetObjectField(TEXT("Stroke"), DefaultStrokeJson());
        }
        if (!Material->HasField(TEXT("DropShadow")))
        {
            Material->SetObjectField(
                TEXT("DropShadow"),
                DefaultShadowJson());
        }
        if (!Material->HasField(TEXT("InnerShadow")))
        {
            Material->SetObjectField(
                TEXT("InnerShadow"),
                DefaultShadowJson());
        }
        if (!Material->HasField(TEXT("VisualPadding")))
        {
            Material->SetObjectField(
                TEXT("VisualPadding"),
                MarginJson(0.0, 0.0, 0.0, 0.0));
        }
    }
}

void AddV2DefaultsToLegacyComponentMaterials(
    const TSharedPtr<FJsonObject>& DocumentObject)
{
    const TArray<TSharedPtr<FJsonValue>>* Components = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Components"), Components)
        || !Components)
    {
        return;
    }
    for (const TSharedPtr<FJsonValue>& ComponentValue : *Components)
    {
        const TSharedPtr<FJsonObject> Component =
            ComponentValue && ComponentValue->Type == EJson::Object
            ? ComponentValue->AsObject()
            : nullptr;
        const TArray<TSharedPtr<FJsonValue>>* ComponentLayers = nullptr;
        if (!Component
            || !Component->TryGetArrayField(
                TEXT("Layers"),
                ComponentLayers)
            || !ComponentLayers)
        {
            continue;
        }
        TSharedPtr<FJsonObject> LayerDocument = MakeShared<FJsonObject>();
        LayerDocument->SetArrayField(TEXT("Layers"), *ComponentLayers);
        AddV2DefaultsToLegacyMaterials(LayerDocument);
    }
}

void AddFixedSizeBindingDefaultsToLayers(
    const TArray<TSharedPtr<FJsonValue>>* Layers)
{
    if (!Layers)
    {
        return;
    }
    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        const TSharedPtr<FJsonObject>* MaterialField = nullptr;
        const TSharedPtr<FJsonObject> Material =
            Layer
            && Layer->TryGetObjectField(TEXT("Material"), MaterialField)
            && MaterialField
            ? *MaterialField
            : nullptr;
        if (Material
            && Material->Values.Num() > 0
            && !Material->HasField(TEXT("SizeBinding")))
        {
            Material->SetStringField(TEXT("SizeBinding"), TEXT("FixedSize"));
        }
    }
}

void AddMaterialSizeBindingDefaults(
    const TSharedPtr<FJsonObject>& DocumentObject)
{
    if (!DocumentObject)
    {
        return;
    }

    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    DocumentObject->TryGetArrayField(TEXT("Layers"), Layers);
    AddFixedSizeBindingDefaultsToLayers(Layers);

    const TArray<TSharedPtr<FJsonValue>>* Components = nullptr;
    if (!DocumentObject->TryGetArrayField(TEXT("Components"), Components)
        || !Components)
    {
        return;
    }
    for (const TSharedPtr<FJsonValue>& ComponentValue : *Components)
    {
        const TSharedPtr<FJsonObject> Component =
            ComponentValue && ComponentValue->Type == EJson::Object
            ? ComponentValue->AsObject()
            : nullptr;
        const TArray<TSharedPtr<FJsonValue>>* ComponentLayers = nullptr;
        if (Component)
        {
            Component->TryGetArrayField(TEXT("Layers"), ComponentLayers);
        }
        AddFixedSizeBindingDefaultsToLayers(ComponentLayers);
    }
}

bool HasRawFieldType(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field,
    const EJson Type)
{
    if (!Object)
    {
        return false;
    }
    const TSharedPtr<FJsonValue>* Value = Object->Values.Find(Field);
    return Value
        && Value->IsValid()
        && !(*Value)->IsNull()
        && (*Value)->Type == Type;
}

bool HasRawIntegerField(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    double Value = 0.0;
    return HasRawFieldType(Object, Field, EJson::Number)
        && Object->TryGetNumberField(Field, Value)
        && FMath::IsFinite(Value)
        && FMath::IsNearlyEqual(Value, FMath::RoundToDouble(Value), 0.000001);
}

TSharedPtr<FJsonObject> RawObjectField(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    const TSharedPtr<FJsonObject>* Value = nullptr;
    if (!Object
        || !Object->TryGetObjectField(Field, Value)
        || !Value
        || !Value->IsValid())
    {
        return nullptr;
    }
    return *Value;
}

bool HasRawVector2(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    const TSharedPtr<FJsonObject> Value = RawObjectField(Object, Field);
    return HasRawFieldType(Value, TEXT("X"), EJson::Number)
        && HasRawFieldType(Value, TEXT("Y"), EJson::Number);
}

bool HasRawVector4(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    const TSharedPtr<FJsonObject> Value = RawObjectField(Object, Field);
    return HasRawFieldType(Value, TEXT("X"), EJson::Number)
        && HasRawFieldType(Value, TEXT("Y"), EJson::Number)
        && HasRawFieldType(Value, TEXT("Z"), EJson::Number)
        && HasRawFieldType(Value, TEXT("W"), EJson::Number);
}

bool HasRawExactFields(
    const TSharedPtr<FJsonObject>& Object,
    const std::initializer_list<const TCHAR*> Fields)
{
    if (!Object || Object->Values.Num() != static_cast<int32>(Fields.size()))
    {
        return false;
    }
    for (const TCHAR* Field : Fields)
    {
        if (!Object->HasField(Field))
        {
            return false;
        }
    }
    return true;
}

bool HasRawStroke(const TSharedPtr<FJsonObject>& Material)
{
    const TSharedPtr<FJsonObject> Stroke = RawObjectField(
        Material,
        TEXT("Stroke"));
    return HasRawFieldType(Stroke, TEXT("Width"), EJson::Number)
        && HasRawFieldType(Stroke, TEXT("Alignment"), EJson::String)
        && HasRawFieldType(Stroke, TEXT("Color"), EJson::String);
}

bool HasRawShadow(
    const TSharedPtr<FJsonObject>& Material,
    const TCHAR* Field)
{
    const TSharedPtr<FJsonObject> Shadow = RawObjectField(Material, Field);
    return HasRawFieldType(Shadow, TEXT("Enabled"), EJson::Boolean)
        && HasRawFieldType(Shadow, TEXT("Color"), EJson::String)
        && HasRawVector2(Shadow, TEXT("Offset"))
        && HasRawFieldType(Shadow, TEXT("Blur"), EJson::Number)
        && HasRawFieldType(Shadow, TEXT("Spread"), EJson::Number);
}

bool HasRawVisualPadding(const TSharedPtr<FJsonObject>& Material)
{
    const TSharedPtr<FJsonObject> Padding = RawObjectField(
        Material,
        TEXT("VisualPadding"));
    return HasRawFieldType(Padding, TEXT("Left"), EJson::Number)
        && HasRawFieldType(Padding, TEXT("Top"), EJson::Number)
        && HasRawFieldType(Padding, TEXT("Right"), EJson::Number)
        && HasRawFieldType(Padding, TEXT("Bottom"), EJson::Number);
}

void AddRawMaterialReason(
    TArray<FString>& Reasons,
    const FString& LayerId,
    const TCHAR* Reason)
{
    Reasons.AddUnique(LayerId + TEXT(":") + Reason);
}

bool RawStringArray(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field,
    const bool bAllowEmptyStrings = false)
{
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Object || !Object->TryGetArrayField(Field, Values) || !Values)
    {
        return false;
    }
    for (const TSharedPtr<FJsonValue>& Value : *Values)
    {
        FString StringValue;
        if (!Value || !Value->TryGetString(StringValue)
            || (!bAllowEmptyStrings && StringValue.IsEmpty()))
        {
            return false;
        }
    }
    return true;
}

bool RawJsonObjectString(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    FString Json;
    TSharedPtr<FJsonObject> Parsed;
    if (!Object || !Object->TryGetStringField(Field, Json))
    {
        return false;
    }
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    return FJsonSerializer::Deserialize(Reader, Parsed) && Parsed.IsValid();
}

bool RawJsonValueString(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    FString Json;
    TSharedPtr<FJsonObject> Wrapper;
    if (!Object || !Object->TryGetStringField(Field, Json))
    {
        return false;
    }
    const FString Wrapped = TEXT("{\"Value\":") + Json + TEXT("}");
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(Wrapped);
    return FJsonSerializer::Deserialize(Reader, Wrapper)
        && Wrapper.IsValid()
        && Wrapper->HasField(TEXT("Value"));
}

TSharedPtr<FJsonObject> ParseRawJsonObjectStringValue(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    FString Json;
    TSharedPtr<FJsonObject> Parsed;
    if (!Object || !Object->TryGetStringField(Field, Json))
    {
        return nullptr;
    }
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    return FJsonSerializer::Deserialize(Reader, Parsed) && Parsed
        ? Parsed
        : nullptr;
}

TSharedPtr<FJsonValue> ParseRawJsonValueStringValue(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field)
{
    FString Json;
    TSharedPtr<FJsonObject> Wrapper;
    if (!Object || !Object->TryGetStringField(Field, Json))
    {
        return nullptr;
    }
    const FString Wrapped = TEXT("{\"Value\":") + Json + TEXT("}");
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(Wrapped);
    if (!FJsonSerializer::Deserialize(Reader, Wrapper) || !Wrapper)
    {
        return nullptr;
    }
    return Wrapper->TryGetField(TEXT("Value"));
}

// Component placements preserve the authoring root Kind for stable identity,
// but generation replaces that leaf with a generated UUserWidget.  Require the
// complete marker shape before exempting such a placement from leaf-only
// validation so a malformed marker cannot hide an invalid native Button.
bool HasValidComponentInstancePayload(
    const FString& LayerId,
    const FString& PayloadJson)
{
    if (LayerId.IsEmpty() || PayloadJson.IsEmpty())
    {
        return false;
    }

    TSharedPtr<FJsonObject> Payload;
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(PayloadJson);
    if (!FJsonSerializer::Deserialize(Reader, Payload) || !Payload)
    {
        return false;
    }

    const TSharedPtr<FJsonObject>* Instance = nullptr;
    FString InstanceId;
    FString ComponentId;
    const TSharedPtr<FJsonObject>* PropertyValues = nullptr;
    const TSharedPtr<FJsonObject>* ResolvedOverrides = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* SlotContents = nullptr;
    if (!Payload->TryGetObjectField(TEXT("component_instance"), Instance)
        || !Instance || !Instance->IsValid()
        || !(*Instance)->TryGetStringField(TEXT("id"), InstanceId)
        || InstanceId != LayerId
        || !(*Instance)->TryGetStringField(
            TEXT("component_id"),
            ComponentId)
        || ComponentId.IsEmpty()
        || !(*Instance)->TryGetObjectField(
            TEXT("property_values"),
            PropertyValues)
        || !PropertyValues || !PropertyValues->IsValid()
        || !(*Instance)->TryGetObjectField(
            TEXT("resolved_overrides"),
            ResolvedOverrides)
        || !ResolvedOverrides || !ResolvedOverrides->IsValid()
        || !(*Instance)->TryGetArrayField(
            TEXT("slot_contents"),
            SlotContents)
        || !SlotContents)
    {
        return false;
    }

    for (const TSharedPtr<FJsonValue>& SlotValue : *SlotContents)
    {
        const TSharedPtr<FJsonObject> Slot =
            SlotValue && SlotValue->Type == EJson::Object
            ? SlotValue->AsObject()
            : nullptr;
        FString SlotName;
        const TArray<TSharedPtr<FJsonValue>>* RootLayerIds = nullptr;
        if (!Slot
            || (!Slot->TryGetStringField(TEXT("slot_name"), SlotName)
                && !Slot->TryGetStringField(TEXT("SlotName"), SlotName))
            || SlotName.IsEmpty()
            || (!Slot->TryGetArrayField(
                    TEXT("root_layer_ids"),
                    RootLayerIds)
                && !Slot->TryGetArrayField(
                    TEXT("RootLayerIds"),
                    RootLayerIds))
            || !RootLayerIds)
        {
            return false;
        }
        for (const TSharedPtr<FJsonValue>& RootValue : *RootLayerIds)
        {
            FString RootLayerId;
            if (!RootValue || !RootValue->TryGetString(RootLayerId)
                || RootLayerId.IsEmpty())
            {
                return false;
            }
        }
    }
    return true;
}

bool HasValidComponentInstancePayload(
    const TSharedPtr<FJsonObject>& Layer)
{
    FString LayerId;
    FString PayloadJson;
    return Layer
        && Layer->TryGetStringField(TEXT("Id"), LayerId)
        && Layer->TryGetStringField(TEXT("PayloadJson"), PayloadJson)
        && HasValidComponentInstancePayload(LayerId, PayloadJson);
}

bool HasValidComponentInstancePayload(
    const FTigerStudioUMGLayerRecord& Layer)
{
    return HasValidComponentInstancePayload(Layer.Id, Layer.PayloadJson);
}

bool JsonObjectsEqualExact(
    const TSharedPtr<FJsonObject>& Left,
    const TSharedPtr<FJsonObject>& Right)
{
    if (!Left || !Right || Left->Values.Num() != Right->Values.Num())
    {
        return false;
    }
    for (const auto& Pair : Left->Values)
    {
        const TSharedPtr<FJsonValue> Other =
            Right->TryGetField(Pair.Key.ToView());
        if (!Pair.Value || !Other
            || !FJsonValue::CompareEqual(*Pair.Value, *Other))
        {
            return false;
        }
    }
    return true;
}

TSharedPtr<FJsonObject> RawImplicitComponentDefaults(
    const TSharedPtr<FJsonObject>& Component)
{
    const TArray<TSharedPtr<FJsonValue>>* Properties = nullptr;
    if (!Component
        || !Component->TryGetArrayField(TEXT("Properties"), Properties)
        || !Properties)
    {
        return nullptr;
    }
    TSharedPtr<FJsonObject> Expected = MakeShared<FJsonObject>();
    for (const TSharedPtr<FJsonValue>& PropertyValue : *Properties)
    {
        const TSharedPtr<FJsonObject> Property =
            PropertyValue && PropertyValue->Type == EJson::Object
            ? PropertyValue->AsObject()
            : nullptr;
        FString Name;
        const TSharedPtr<FJsonValue> DefaultValue =
            ParseRawJsonValueStringValue(Property, TEXT("DefaultValueJson"));
        if (!Property
            || !Property->TryGetStringField(TEXT("Name"), Name)
            || Name.IsEmpty()
            || !DefaultValue)
        {
            return nullptr;
        }
        Expected->SetField(Name, DefaultValue);
    }
    const TSharedPtr<FJsonObject> Variants =
        ParseRawJsonObjectStringValue(Component, TEXT("VariantValuesJson"));
    if (!Variants)
    {
        return nullptr;
    }
    for (const auto& Pair : Variants->Values)
    {
        Expected->SetField(Pair.Key, Pair.Value);
    }
    return Expected;
}

TSharedPtr<FJsonObject> RawLayerValidationDocument(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    if (!DocumentObject || SchemaVersion < ComponentSchemaVersion)
    {
        return DocumentObject;
    }
    TSharedPtr<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->Values = DocumentObject->Values;
    TArray<TSharedPtr<FJsonValue>> CombinedLayers;
    const TArray<TSharedPtr<FJsonValue>>* ScreenLayers = nullptr;
    if (DocumentObject->TryGetArrayField(TEXT("Layers"), ScreenLayers)
        && ScreenLayers)
    {
        CombinedLayers.Append(*ScreenLayers);
    }
    const TArray<TSharedPtr<FJsonValue>>* Components = nullptr;
    if (DocumentObject->TryGetArrayField(TEXT("Components"), Components)
        && Components)
    {
        for (const TSharedPtr<FJsonValue>& ComponentValue : *Components)
        {
            const TSharedPtr<FJsonObject> Component =
                ComponentValue && ComponentValue->Type == EJson::Object
                ? ComponentValue->AsObject()
                : nullptr;
            const TArray<TSharedPtr<FJsonValue>>* ComponentLayers = nullptr;
            if (Component
                && Component->TryGetArrayField(
                    TEXT("Layers"),
                    ComponentLayers)
                && ComponentLayers)
            {
                CombinedLayers.Append(*ComponentLayers);
            }
        }
    }
    Result->SetArrayField(TEXT("Layers"), CombinedLayers);
    return Result;
}

TArray<FString> ValidateRawComponentRecords(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    if (!DocumentObject)
    {
        return Reasons;
    }
    const bool bHasComponents = DocumentObject->HasField(TEXT("Components"));
    const bool bHasInstances =
        DocumentObject->HasField(TEXT("ComponentInstances"));
    if (SchemaVersion < ComponentSchemaVersion)
    {
        const TArray<TSharedPtr<FJsonValue>>* LegacyComponents = nullptr;
        const TArray<TSharedPtr<FJsonValue>>* LegacyInstances = nullptr;
        const bool bNonEmptyOrMalformedComponents = bHasComponents
            && (!DocumentObject->TryGetArrayField(
                    TEXT("Components"),
                    LegacyComponents)
                || !LegacyComponents
                || !LegacyComponents->IsEmpty());
        const bool bNonEmptyOrMalformedInstances = bHasInstances
            && (!DocumentObject->TryGetArrayField(
                    TEXT("ComponentInstances"),
                    LegacyInstances)
                || !LegacyInstances
                || !LegacyInstances->IsEmpty());
        if (bNonEmptyOrMalformedComponents || bNonEmptyOrMalformedInstances)
        {
            Reasons.Add(TEXT("umg_components_require_schema_18"));
        }
        return Reasons;
    }

    const TArray<TSharedPtr<FJsonValue>>* Components = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Instances = nullptr;
    if (!DocumentObject->TryGetArrayField(TEXT("Components"), Components)
        || !Components)
    {
        Reasons.Add(TEXT("umg_components_record_invalid"));
    }
    if (!DocumentObject->TryGetArrayField(
            TEXT("ComponentInstances"),
            Instances)
        || !Instances)
    {
        Reasons.Add(TEXT("umg_component_instances_record_invalid"));
    }
    if (!Components || !Instances)
    {
        return Reasons;
    }

    TSet<FString> RawScreenLayerIds;
    const TArray<TSharedPtr<FJsonValue>>* ScreenLayers = nullptr;
    if (DocumentObject->TryGetArrayField(TEXT("Layers"), ScreenLayers)
        && ScreenLayers)
    {
        for (const TSharedPtr<FJsonValue>& LayerValue : *ScreenLayers)
        {
            const TSharedPtr<FJsonObject> Layer =
                LayerValue && LayerValue->Type == EJson::Object
                ? LayerValue->AsObject()
                : nullptr;
            FString LayerId;
            if (Layer && Layer->TryGetStringField(TEXT("Id"), LayerId)
                && !LayerId.IsEmpty())
            {
                RawScreenLayerIds.Add(LayerId);
            }
        }
    }
    TMap<FString, TSharedPtr<FJsonObject>> RawComponentsById;
    TMap<FString, FString> RawComponentRootById;
    TMap<FString, FString> RawDefinitionOwnerByLayer;

    for (const TSharedPtr<FJsonValue>& ComponentValue : *Components)
    {
        const TSharedPtr<FJsonObject> Component =
            ComponentValue && ComponentValue->Type == EJson::Object
            ? ComponentValue->AsObject()
            : nullptr;
        FString ComponentId;
        FString Name;
        FString RootLayerId;
        FString BaseComponentId;
        const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
        const TArray<TSharedPtr<FJsonValue>>* Properties = nullptr;
        const TArray<TSharedPtr<FJsonValue>>* Slots = nullptr;
        if (!Component
            || !Component->TryGetStringField(TEXT("Id"), ComponentId)
            || ComponentId.IsEmpty()
            || !Component->TryGetStringField(TEXT("Name"), Name)
            || !Component->TryGetStringField(
                TEXT("RootLayerId"),
                RootLayerId)
            || RootLayerId.IsEmpty()
            || !Component->TryGetStringField(
                TEXT("BaseComponentId"),
                BaseComponentId)
            || !RawJsonObjectString(Component, TEXT("VariantValuesJson"))
            || !RawStringArray(Component, TEXT("DependencyComponentIds"))
            || !Component->TryGetArrayField(TEXT("Layers"), Layers)
            || !Layers
            || !Component->TryGetArrayField(TEXT("Properties"), Properties)
            || !Properties
            || !Component->TryGetArrayField(TEXT("Slots"), Slots)
            || !Slots)
        {
            Reasons.AddUnique(TEXT("umg_component_record_invalid"));
            continue;
        }
        RawComponentsById.Add(ComponentId, Component);
        RawComponentRootById.Add(ComponentId, RootLayerId);
        for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
        {
            const TSharedPtr<FJsonObject> Layer =
                LayerValue && LayerValue->Type == EJson::Object
                ? LayerValue->AsObject()
                : nullptr;
            if (!Layer)
            {
                Reasons.AddUnique(TEXT("umg_component_layer_record_invalid"));
                continue;
            }
            FString DefinitionLayerId;
            if (Layer->TryGetStringField(TEXT("Id"), DefinitionLayerId)
                && !DefinitionLayerId.IsEmpty()
                && !RawDefinitionOwnerByLayer.Contains(DefinitionLayerId))
            {
                RawDefinitionOwnerByLayer.Add(
                    DefinitionLayerId,
                    ComponentId);
            }
        }
        for (const TSharedPtr<FJsonValue>& PropertyValue : *Properties)
        {
            const TSharedPtr<FJsonObject> Property =
                PropertyValue && PropertyValue->Type == EJson::Object
                ? PropertyValue->AsObject()
                : nullptr;
            FString PropertyName;
            FString PropertyType;
            FString Description;
            const TArray<TSharedPtr<FJsonValue>>* Bindings = nullptr;
            if (!Property
                || !Property->TryGetStringField(
                    TEXT("Name"),
                    PropertyName)
                || PropertyName.IsEmpty()
                || !Property->TryGetStringField(
                    TEXT("Type"),
                    PropertyType)
                || (PropertyType != TEXT("text")
                    && PropertyType != TEXT("boolean")
                    && PropertyType != TEXT("number")
                    && PropertyType != TEXT("enum")
                    && PropertyType != TEXT("instance_swap")
                    && PropertyType != TEXT("slot"))
                || !RawJsonValueString(Property, TEXT("DefaultValueJson"))
                || !RawStringArray(Property, TEXT("Values"), true)
                || !Property->TryGetStringField(
                    TEXT("Description"),
                    Description)
                || !Property->TryGetArrayField(TEXT("Bindings"), Bindings)
                || !Bindings)
            {
                Reasons.AddUnique(
                    TEXT("umg_component_property_record_invalid"));
                continue;
            }
            for (const TSharedPtr<FJsonValue>& BindingValue : *Bindings)
            {
                const TSharedPtr<FJsonObject> Binding =
                    BindingValue && BindingValue->Type == EJson::Object
                    ? BindingValue->AsObject()
                    : nullptr;
                FString LayerId;
                FString TargetPath;
                if (!Binding
                    || !Binding->TryGetStringField(TEXT("LayerId"), LayerId)
                    || LayerId.IsEmpty()
                    || !Binding->TryGetStringField(
                        TEXT("TargetPath"),
                        TargetPath)
                    || TargetPath.IsEmpty())
                {
                    Reasons.AddUnique(
                        TEXT("umg_component_property_binding_record_invalid"));
                }
            }
        }
        for (const TSharedPtr<FJsonValue>& SlotValue : *Slots)
        {
            const TSharedPtr<FJsonObject> Slot =
                SlotValue && SlotValue->Type == EJson::Object
                ? SlotValue->AsObject()
                : nullptr;
            FString SlotName;
            FString LayerId;
            bool bExpose = false;
            if (!Slot
                || !Slot->TryGetStringField(TEXT("Name"), SlotName)
                || SlotName.IsEmpty()
                || !Slot->TryGetStringField(TEXT("LayerId"), LayerId)
                || LayerId.IsEmpty()
                || !Slot->TryGetBoolField(
                    TEXT("ExposeOnInstanceOnly"),
                    bExpose))
            {
                Reasons.AddUnique(TEXT("umg_component_slot_record_invalid"));
            }
        }
    }

    TSet<FString> RawImplicitDefinitionPlacementIds;
    for (const TSharedPtr<FJsonValue>& InstanceValue : *Instances)
    {
        const TSharedPtr<FJsonObject> Instance =
            InstanceValue && InstanceValue->Type == EJson::Object
            ? InstanceValue->AsObject()
            : nullptr;
        FString Id;
        FString ComponentId;
        FString LayerId;
        FString ParentId;
        const TArray<TSharedPtr<FJsonValue>>* SlotContents = nullptr;
        if (!Instance
            || !Instance->TryGetStringField(TEXT("Id"), Id)
            || Id.IsEmpty()
            || !Instance->TryGetStringField(
                TEXT("ComponentId"),
                ComponentId)
            || ComponentId.IsEmpty()
            || !Instance->TryGetStringField(TEXT("LayerId"), LayerId)
            || LayerId.IsEmpty()
            || !Instance->TryGetStringField(TEXT("ParentId"), ParentId)
            || !RawJsonObjectString(Instance, TEXT("PropertyValuesJson"))
            || !RawJsonObjectString(Instance, TEXT("ResolvedOverridesJson"))
            || !Instance->TryGetArrayField(
                TEXT("SlotContents"),
                SlotContents)
            || !SlotContents)
        {
            Reasons.AddUnique(
                TEXT("umg_component_instance_record_invalid"));
            continue;
        }
        const FString* DefinitionOwner =
            RawDefinitionOwnerByLayer.Find(LayerId);
        const FString* ComponentRoot =
            RawComponentRootById.Find(ComponentId);
        const bool bImplicitDefinitionPlacement =
            Id == LayerId
            && DefinitionOwner && *DefinitionOwner == ComponentId
            && ComponentRoot && *ComponentRoot == LayerId;
        if (bImplicitDefinitionPlacement)
        {
            RawImplicitDefinitionPlacementIds.Add(LayerId);
            const TSharedPtr<FJsonObject>* Component =
                RawComponentsById.Find(ComponentId);
            const TSharedPtr<FJsonObject> Expected = Component
                ? RawImplicitComponentDefaults(*Component)
                : nullptr;
            const TSharedPtr<FJsonObject> Actual =
                ParseRawJsonObjectStringValue(
                    Instance,
                    TEXT("PropertyValuesJson"));
            if (Expected && Actual
                && !JsonObjectsEqualExact(Expected, Actual))
            {
                Reasons.AddUnique(
                    TEXT("umg_implicit_component_property_values_not_default"));
            }
        }
        for (const TSharedPtr<FJsonValue>& SlotContentValue : *SlotContents)
        {
            const TSharedPtr<FJsonObject> SlotContent =
                SlotContentValue && SlotContentValue->Type == EJson::Object
                ? SlotContentValue->AsObject()
                : nullptr;
            FString SlotName;
            if (!SlotContent
                || !SlotContent->TryGetStringField(
                    TEXT("SlotName"),
                    SlotName)
                || SlotName.IsEmpty()
                || !RawStringArray(SlotContent, TEXT("RootLayerIds")))
            {
                Reasons.AddUnique(
                    TEXT("umg_component_instance_slot_content_record_invalid"));
            }
        }
    }
    for (const TPair<FString, FString>& Pair : RawDefinitionOwnerByLayer)
    {
        if (RawScreenLayerIds.Contains(Pair.Key)
            && !RawImplicitDefinitionPlacementIds.Contains(Pair.Key))
        {
            Reasons.AddUnique(
                TEXT("umg_component_definition_layer_leaked_to_screen"));
            break;
        }
    }
    return Reasons;
}

TArray<FString> ValidateRawDocumentRecords(
    const TSharedPtr<FJsonObject>& DocumentObject)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        Reasons.Add(TEXT("umg_layers_record_invalid"));
    }
    else
    {
        for (int32 Index = 0; Index < Layers->Num(); ++Index)
        {
            const TSharedPtr<FJsonValue>& LayerValue = (*Layers)[Index];
            const TSharedPtr<FJsonObject> Layer =
                LayerValue && LayerValue->Type == EJson::Object
                ? LayerValue->AsObject()
                : nullptr;
            if (!Layer)
            {
                Reasons.AddUnique(TEXT("umg_layer_record_invalid"));
                continue;
            }
            FString Disposition;
            FString LayerId;
            Layer->TryGetStringField(TEXT("Id"), LayerId);
            const bool bDispositionValid =
                Layer->TryGetStringField(TEXT("Disposition"), Disposition)
                && (Disposition == TEXT("Native")
                    || Disposition == TEXT("Material")
                    || Disposition == TEXT("Baked")
                    || Disposition == TEXT("Blocked"));
            if (!bDispositionValid)
            {
                Reasons.AddUnique(
                    (LayerId.IsEmpty()
                        ? FString::Printf(TEXT("layer[%d]"), Index)
                        : LayerId)
                    + TEXT(":umg_layer_disposition_invalid"));
            }
        }
    }

    if (DocumentObject && DocumentObject->HasField(TEXT("Resources")))
    {
        const TArray<TSharedPtr<FJsonValue>>* Resources = nullptr;
        if (!DocumentObject->TryGetArrayField(TEXT("Resources"), Resources)
            || !Resources)
        {
            Reasons.AddUnique(TEXT("umg_resources_record_invalid"));
        }
        else
        {
            for (const TSharedPtr<FJsonValue>& ResourceValue : *Resources)
            {
                if (!ResourceValue || ResourceValue->Type != EJson::Object)
                {
                    Reasons.AddUnique(TEXT("umg_resource_record_invalid"));
                }
            }
        }
    }
    return Reasons;
}

bool TryGetFiniteNumber(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field,
    double& OutValue);

TArray<FString> ValidateRawPanelRecords(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }
    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        if (!Layer)
        {
            continue;
        }
        FString LayerId = TEXT("<unknown>");
        FString Kind;
        FString PanelKind = TEXT("None");
        FString SpacingStrategy = TEXT("Padding");
        FString SpacerSizeRule = TEXT("Auto");
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        Layer->TryGetStringField(TEXT("Kind"), Kind);
        const bool bPanelKindTyped = !Layer->HasField(TEXT("PanelKind"))
            || Layer->TryGetStringField(TEXT("PanelKind"), PanelKind);
        if (!bPanelKindTyped)
        {
            Reasons.AddUnique(
                LayerId + TEXT(":umg_panel_kind_record_invalid"));
            continue;
        }
        if (PanelKind == TEXT("Overlay")
            && SchemaVersion < OverlayPanelSchemaVersion)
        {
            Reasons.AddUnique(
                LayerId + TEXT(":umg_overlay_panel_requires_schema_17"));
        }
        const bool bIsGroup = Kind == TEXT("Group");
        const bool bSpacingRequired =
            SchemaVersion >= SpacingStrategySchemaVersion;
        if ((bSpacingRequired || Layer->HasField(TEXT("SpacingStrategy")))
            && !Layer->TryGetStringField(
                TEXT("SpacingStrategy"),
                SpacingStrategy))
        {
            Reasons.AddUnique(
                LayerId + TEXT(":umg_spacing_strategy_record_invalid"));
        }
        if ((bSpacingRequired || Layer->HasField(TEXT("SpacerSizeRule")))
            && !Layer->TryGetStringField(
                TEXT("SpacerSizeRule"),
                SpacerSizeRule))
        {
            Reasons.AddUnique(
                LayerId + TEXT(":umg_spacer_size_rule_record_invalid"));
        }
        double SpacerFillCoefficient = 1.0;
        if ((bSpacingRequired
                || Layer->HasField(TEXT("SpacerFillCoefficient")))
            && (!TryGetFiniteNumber(
                    Layer,
                    TEXT("SpacerFillCoefficient"),
                    SpacerFillCoefficient)
                || SpacerFillCoefficient <= 0.0))
        {
            Reasons.AddUnique(
                LayerId + TEXT(":umg_spacer_fill_coefficient_invalid"));
        }
        if (SpacingStrategy != TEXT("Padding")
            && SpacingStrategy != TEXT("Spacer"))
        {
            Reasons.AddUnique(
                LayerId + TEXT(":umg_spacing_strategy_unsupported"));
        }
        if (SpacerSizeRule != TEXT("Auto")
            && SpacerSizeRule != TEXT("Fill"))
        {
            Reasons.AddUnique(
                LayerId + TEXT(":umg_spacer_size_rule_unsupported"));
        }
        if (SchemaVersion < SpacingStrategySchemaVersion
            && SpacingStrategy != TEXT("Padding"))
        {
            Reasons.AddUnique(
                LayerId + TEXT(":umg_spacing_strategy_requires_schema_17"));
        }
        if (!bIsGroup)
        {
            if (SpacingStrategy != TEXT("Padding"))
            {
                Reasons.AddUnique(
                    LayerId
                    + TEXT(
                        ":umg_non_group_spacing_strategy_must_be_padding"));
            }
            if (SpacerSizeRule != TEXT("Auto"))
            {
                Reasons.AddUnique(
                    LayerId
                    + TEXT(
                        ":umg_non_group_spacer_size_rule_must_be_auto"));
            }
            if (!FMath::IsNearlyEqual(
                    SpacerFillCoefficient,
                    1.0,
                    0.000001))
            {
                Reasons.AddUnique(
                    LayerId
                    + TEXT(
                        ":umg_non_group_spacer_fill_coefficient_must_be_one"));
            }
        }
        else if (SpacingStrategy == TEXT("Spacer")
            && PanelKind != TEXT("Horizontal")
            && PanelKind != TEXT("Vertical"))
        {
            Reasons.AddUnique(
                LayerId
                + TEXT(":umg_spacer_strategy_requires_linear_panel"));
        }
    }
    return Reasons;
}

TArray<FString> ValidateRawV2MaterialLayers(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        const TSharedPtr<FJsonObject> Material = RawObjectField(
            Layer,
            TEXT("Material"));
        if (!Layer || !Material)
        {
            continue;
        }

        FString Schema;
        FString Generator;
        FString Kind;
        Material->TryGetStringField(TEXT("Schema"), Schema);
        Material->TryGetStringField(TEXT("Generator"), Generator);
        Material->TryGetStringField(TEXT("Kind"), Kind);
        const bool bRoundedCard =
            Schema == TEXT("tigerstudio.umg.ui_material.v2")
            || Generator
                == TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1")
            || Kind == TEXT("RoundedCard")
            || Material->HasField(TEXT("CornerRadii"))
            || Material->HasField(TEXT("CornerSmoothing"))
            || Material->HasField(TEXT("Stroke"))
            || Material->HasField(TEXT("DropShadow"))
            || Material->HasField(TEXT("InnerShadow"))
            || Material->HasField(TEXT("VisualPadding"));
        if (!bRoundedCard)
        {
            continue;
        }

        FString LayerId = TEXT("<unknown>");
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        FString CoordinateSpace;
        Material->TryGetStringField(
            TEXT("CoordinateSpace"),
            CoordinateSpace);
        if (Schema != TEXT("tigerstudio.umg.ui_material.v2"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_schema_unsupported"));
        }
        if (Generator
            != TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_generator_unsupported"));
        }
        if (Kind != TEXT("RoundedCard"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_kind_unsupported"));
        }
        if (CoordinateSpace != TEXT("LocalUV"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_coordinate_space_unsupported"));
        }
        if (!HasRawVector2(Material, TEXT("Size")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_size_invalid"));
        }
        FString SizeBinding = TEXT("FixedSize");
        const bool bSizeBindingPresent =
            Material->HasField(TEXT("SizeBinding"));
        const bool bHasSizeBinding = Material->TryGetStringField(
            TEXT("SizeBinding"),
            SizeBinding);
        if (bSizeBindingPresent && !bHasSizeBinding)
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_size_binding_invalid"));
        }
        else if (!bSizeBindingPresent
            && SchemaVersion >= DynamicRoundedCardSizeSchemaVersion)
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_size_binding_invalid"));
        }
        else if (bHasSizeBinding
            && SizeBinding != TEXT("FixedSize")
            && SizeBinding != TEXT("WidgetGeometry"))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_size_binding_invalid"));
        }
        if (SizeBinding == TEXT("WidgetGeometry")
            && SchemaVersion < DynamicRoundedCardSizeSchemaVersion)
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_dynamic_size_binding_requires_schema_19"));
        }
        if (!HasRawFieldType(Material, TEXT("FillKind"), EJson::String))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_fill_kind_unsupported"));
        }
        if (!HasRawFieldType(Material, TEXT("FillColor"), EJson::String))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_fill_color_invalid"));
        }
        if (!HasRawFieldType(Material, TEXT("Opacity"), EJson::Number))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_opacity_invalid"));
        }
        if (!HasRawVector2(Material, TEXT("Start"))
            || !HasRawVector2(Material, TEXT("End"))
            || !HasRawVector2(Material, TEXT("Width")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_gradient_geometry_invalid"));
        }

        const TArray<TSharedPtr<FJsonValue>>* Stops = nullptr;
        if (!Material->TryGetArrayField(TEXT("Stops"), Stops)
            || !Stops
            || Stops->Num() < 2)
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_gradient_requires_two_stops"));
        }
        else if (Stops->Num() > 16)
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_gradient_stop_limit_exceeded"));
        }
        else
        {
            for (const TSharedPtr<FJsonValue>& StopValue : *Stops)
            {
                const TSharedPtr<FJsonObject> Stop =
                    StopValue && StopValue->Type == EJson::Object
                    ? StopValue->AsObject()
                    : nullptr;
                if (!HasRawFieldType(
                        Stop,
                        TEXT("Position"),
                        EJson::Number)
                    || !HasRawFieldType(
                        Stop,
                        TEXT("Color"),
                        EJson::String))
                {
                    AddRawMaterialReason(
                        Reasons,
                        LayerId,
                        TEXT("ui_material_gradient_stop_invalid"));
                    break;
                }
            }
        }
        if (!HasRawVector4(Material, TEXT("CornerRadii")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_radii_invalid"));
        }
        if (!HasRawFieldType(
                Material,
                TEXT("CornerSmoothing"),
                EJson::Number))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_smoothing_invalid"));
        }
        if (!HasRawStroke(Material))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_stroke_invalid"));
        }
        if (!HasRawShadow(Material, TEXT("DropShadow")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_drop_shadow_invalid"));
        }
        if (!HasRawShadow(Material, TEXT("InnerShadow")))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_rounded_card_inner_shadow_invalid"));
        }
        if (!HasRawVisualPadding(Material))
        {
            AddRawMaterialReason(
                Reasons,
                LayerId,
                TEXT("ui_material_visual_padding_invalid"));
        }
    }
    return Reasons;
}

TArray<FString> ValidateRawImageFillLayers(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        const TSharedPtr<FJsonObject> ImageFill = RawObjectField(
            Layer,
            TEXT("ImageFill"));
        if (!Layer || !ImageFill || ImageFill->Values.IsEmpty())
        {
            continue;
        }

        FString LayerId = TEXT("<unknown>");
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        const auto AddReason = [&Reasons, &LayerId](const TCHAR* Reason)
        {
            Reasons.AddUnique(LayerId + TEXT(":") + Reason);
        };
        if (SchemaVersion < 11)
        {
            AddReason(TEXT("image_fill_requires_schema_11"));
        }

        FString AssetId;
        if (!ImageFill->TryGetStringField(TEXT("AssetId"), AssetId)
            || AssetId.IsEmpty())
        {
            AddReason(TEXT("image_fill_asset_id_missing"));
        }
        if (!HasRawFieldType(ImageFill, TEXT("Mode"), EJson::String))
        {
            AddReason(TEXT("image_fill_mode_unsupported"));
        }
        if (!HasRawVector2(ImageFill, TEXT("SourceSize")))
        {
            AddReason(TEXT("image_fill_source_size_invalid"));
        }
        if (!HasRawVector2(ImageFill, TEXT("FocalPoint")))
        {
            AddReason(TEXT("image_fill_focal_point_invalid"));
        }
        if (!HasRawFieldType(ImageFill, TEXT("TileScale"), EJson::Number))
        {
            AddReason(TEXT("image_fill_tile_scale_invalid"));
        }
        if (!HasRawFieldType(ImageFill, TEXT("Opacity"), EJson::Number))
        {
            AddReason(TEXT("image_fill_opacity_invalid"));
        }
        if (!HasRawFieldType(ImageFill, TEXT("Tint"), EJson::String))
        {
            AddReason(TEXT("image_fill_tint_invalid"));
        }
        if (!HasRawVector4(ImageFill, TEXT("CornerRadii")))
        {
            AddReason(TEXT("image_fill_corner_radii_invalid"));
        }

        const TSharedPtr<FJsonObject> Crop = RawObjectField(
            ImageFill,
            TEXT("Crop"));
        if (!HasRawFieldType(Crop, TEXT("Enabled"), EJson::Boolean)
            || !HasRawFieldType(Crop, TEXT("Units"), EJson::String)
            || !HasRawFieldType(Crop, TEXT("X"), EJson::Number)
            || !HasRawFieldType(Crop, TEXT("Y"), EJson::Number)
            || !HasRawFieldType(Crop, TEXT("Width"), EJson::Number)
            || !HasRawFieldType(Crop, TEXT("Height"), EJson::Number))
        {
            AddReason(TEXT("image_fill_crop_record_invalid"));
        }

        const TSharedPtr<FJsonObject> Adjustments = RawObjectField(
            ImageFill,
            TEXT("Adjustments"));
        if (!HasRawFieldType(
                Adjustments,
                TEXT("Exposure"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Contrast"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Saturation"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Temperature"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Tint"),
                EJson::Number)
            || !HasRawFieldType(
                Adjustments,
                TEXT("Highlights"),
                EJson::Number))
        {
            AddReason(TEXT("image_fill_adjustments_record_invalid"));
        }

        const TSharedPtr<FJsonObject> NineSlice = RawObjectField(
            ImageFill,
            TEXT("NineSlice"));
        if (!HasRawFieldType(NineSlice, TEXT("Enabled"), EJson::Boolean)
            || !HasRawFieldType(NineSlice, TEXT("Units"), EJson::String)
            || !HasRawFieldType(NineSlice, TEXT("Left"), EJson::Number)
            || !HasRawFieldType(NineSlice, TEXT("Top"), EJson::Number)
            || !HasRawFieldType(NineSlice, TEXT("Right"), EJson::Number)
            || !HasRawFieldType(NineSlice, TEXT("Bottom"), EJson::Number))
        {
            AddReason(TEXT("image_fill_nine_slice_record_invalid"));
        }
    }
    return Reasons;
}

TArray<FString> ValidateRawButtonStateRecord(
    const TSharedPtr<FJsonObject>& State,
    const FString& Prefix)
{
    TArray<FString> Reasons;
    if (!State)
    {
        Reasons.Add(Prefix + TEXT("_invalid"));
        return Reasons;
    }
    const TSharedPtr<FJsonObject> CornerRadii = RawObjectField(
        State,
        TEXT("CornerRadii"));
    const auto HasFiniteNumberInRange = [State](
        const TCHAR* Field,
        const double Minimum,
        const double Maximum)
    {
        double Value = 0.0;
        return HasRawFieldType(State, Field, EJson::Number)
            && State->TryGetNumberField(Field, Value)
            && FMath::IsFinite(Value)
            && Value >= Minimum
            && Value <= Maximum;
    };
    if (!HasRawExactFields(
            State,
            {TEXT("Fill"),
             TEXT("Stroke"),
             TEXT("StrokeWidth"),
             TEXT("CornerRadii"),
             TEXT("TextColor"),
             TEXT("FontSize"),
             TEXT("FontWeight"),
             TEXT("Opacity")}))
    {
        Reasons.Add(Prefix + TEXT("_fields_invalid"));
    }
    if (!HasRawFieldType(State, TEXT("Fill"), EJson::String))
    {
        Reasons.Add(Prefix + TEXT("_fill_invalid"));
    }
    if (!HasRawFieldType(State, TEXT("Stroke"), EJson::String))
    {
        Reasons.Add(Prefix + TEXT("_stroke_invalid"));
    }
    if (!HasFiniteNumberInRange(TEXT("StrokeWidth"), 0.0, 1024.0))
    {
        Reasons.Add(Prefix + TEXT("_stroke_width_invalid"));
    }
    if (!HasRawExactFields(
            CornerRadii,
            {TEXT("X"), TEXT("Y"), TEXT("Z"), TEXT("W")})
        || !HasRawVector4(State, TEXT("CornerRadii")))
    {
        Reasons.Add(Prefix + TEXT("_corner_radii_invalid"));
    }
    else
    {
        for (const TCHAR* Field : {
                 TEXT("X"), TEXT("Y"), TEXT("Z"), TEXT("W")})
        {
            double Value = 0.0;
            if (!CornerRadii->TryGetNumberField(Field, Value)
                || !FMath::IsFinite(Value)
                || Value < 0.0
                || Value > 8192.0)
            {
                Reasons.Add(Prefix + TEXT("_corner_radii_invalid"));
                break;
            }
        }
    }
    if (!HasRawFieldType(State, TEXT("TextColor"), EJson::String))
    {
        Reasons.Add(Prefix + TEXT("_text_color_invalid"));
    }
    if (!HasFiniteNumberInRange(TEXT("FontSize"), 1.0, 512.0))
    {
        Reasons.Add(Prefix + TEXT("_font_size_invalid"));
    }
    double FontWeight = 0.0;
    if (!HasRawIntegerField(State, TEXT("FontWeight"))
        || !State->TryGetNumberField(TEXT("FontWeight"), FontWeight)
        || FontWeight < 100.0
        || FontWeight > 900.0)
    {
        Reasons.Add(Prefix + TEXT("_font_weight_invalid"));
    }
    if (!HasFiniteNumberInRange(TEXT("Opacity"), 0.0, 1.0))
    {
        Reasons.Add(Prefix + TEXT("_opacity_invalid"));
    }
    return Reasons;
}

TArray<FString> ValidateRawButtonStyleLayers(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        if (!Layer)
        {
            continue;
        }

        FString LayerId = TEXT("<unknown>");
        FString LayerKind;
        FString LayerDisposition;
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        Layer->TryGetStringField(TEXT("Kind"), LayerKind);
        Layer->TryGetStringField(TEXT("Disposition"), LayerDisposition);
        if (HasValidComponentInstancePayload(Layer))
        {
            continue;
        }
        const bool bButtonLayer = LayerKind == TEXT("Button");
        const bool bNativeButtonLayer = bButtonLayer
            && LayerDisposition == TEXT("Native");
        const auto AddReason = [&Reasons, &LayerId](const FString& Reason)
        {
            Reasons.AddUnique(LayerId + TEXT(":") + Reason);
        };

        const TSharedPtr<FJsonValue>* RawStyleValue =
            Layer->Values.Find(TEXT("ButtonStyle"));
        if (!RawStyleValue || !RawStyleValue->IsValid()
            || (*RawStyleValue)->IsNull())
        {
            if (SchemaVersion >= ButtonStyleSchemaVersion
                && bNativeButtonLayer)
            {
                AddReason(TEXT("button_style_missing"));
            }
            continue;
        }
        if ((*RawStyleValue)->Type != EJson::Object)
        {
            AddReason(TEXT("button_style_missing"));
            continue;
        }

        const TSharedPtr<FJsonObject> ButtonStyle =
            (*RawStyleValue)->AsObject();
        if (!ButtonStyle || ButtonStyle->Values.IsEmpty())
        {
            if (SchemaVersion >= ButtonStyleSchemaVersion
                && bNativeButtonLayer)
            {
                AddReason(TEXT("button_style_missing"));
            }
            continue;
        }
        if (SchemaVersion < ButtonStyleSchemaVersion)
        {
            AddReason(TEXT("button_style_requires_schema_16"));
            continue;
        }
        if (!bButtonLayer)
        {
            AddReason(TEXT("button_style_layer_kind_unsupported"));
            continue;
        }

        if (!HasRawExactFields(
                ButtonStyle,
                {TEXT("Schema"),
                 TEXT("Enabled"),
                 TEXT("Normal"),
                 TEXT("Hovered"),
                 TEXT("Pressed"),
             TEXT("Disabled")}))
        {
            AddReason(TEXT("button_style_record_fields_invalid"));
        }
        if (!HasRawFieldType(
                ButtonStyle,
                TEXT("Enabled"),
                EJson::Boolean))
        {
            AddReason(TEXT("button_style_enabled_invalid"));
        }

        FString Schema;
        if (!ButtonStyle->TryGetStringField(TEXT("Schema"), Schema)
            || Schema != ButtonStyleSchema)
        {
            AddReason(TEXT("button_style_schema_unsupported"));
        }
        const TCHAR* const StateFields[] = {
            TEXT("Normal"),
            TEXT("Hovered"),
            TEXT("Pressed"),
            TEXT("Disabled")};
        const TCHAR* const StatePrefixes[] = {
            TEXT("button_style_normal"),
            TEXT("button_style_hovered"),
            TEXT("button_style_pressed"),
            TEXT("button_style_disabled")};
        for (int32 StateIndex = 0; StateIndex < UE_ARRAY_COUNT(StateFields);
             ++StateIndex)
        {
            for (const FString& Reason : ValidateRawButtonStateRecord(
                     RawObjectField(
                         ButtonStyle,
                         StateFields[StateIndex]),
                     StatePrefixes[StateIndex]))
            {
                AddReason(Reason);
            }
        }
    }
    return Reasons;
}

TArray<FString> ValidateRawLayerVisibility(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }
    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        if (!Layer)
        {
            continue;
        }
        FString LayerId = TEXT("<unknown>");
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        const auto AddReason = [&Reasons, &LayerId](const TCHAR* Reason)
        {
            Reasons.AddUnique(LayerId + TEXT(":") + Reason);
        };
        const bool bVisibilityRequired =
            SchemaVersion >= LayerVisibilitySchemaVersion;
        if (!Layer->HasField(TEXT("Visibility")))
        {
            if (bVisibilityRequired)
            {
                AddReason(TEXT("umg_visibility_record_invalid"));
            }
            continue;
        }
        if (!HasRawFieldType(Layer, TEXT("Visibility"), EJson::String))
        {
            AddReason(TEXT("umg_visibility_record_invalid"));
            continue;
        }
        FString Visibility;
        Layer->TryGetStringField(TEXT("Visibility"), Visibility);
        if (SchemaVersion < LayerVisibilitySchemaVersion)
        {
            if (Visibility != TEXT("Visible"))
            {
                AddReason(TEXT("umg_visibility_requires_schema_16"));
            }
            continue;
        }
        if (Visibility != TEXT("Visible")
            && Visibility != TEXT("HitTestInvisible"))
        {
            AddReason(TEXT("umg_visibility_unsupported"));
        }
    }
    return Reasons;
}

TArray<FString> ValidateRawFlipbookLayers(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }

    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        const TSharedPtr<FJsonObject> Flipbook = RawObjectField(
            Layer,
            TEXT("Flipbook"));
        if (!Layer || !Flipbook || Flipbook->Values.IsEmpty())
        {
            continue;
        }

        FString LayerId = TEXT("<unknown>");
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        const auto AddReason = [&Reasons, &LayerId](const TCHAR* Reason)
        {
            Reasons.AddUnique(LayerId + TEXT(":") + Reason);
        };
        if (SchemaVersion < 12)
        {
            AddReason(TEXT("flipbook_requires_schema_12"));
        }
        for (const TCHAR* Field : {
                 TEXT("Schema"),
                 TEXT("Generator"),
                 TEXT("Kind"),
                 TEXT("CoordinateSpace"),
                 TEXT("AssetId")})
        {
            if (!HasRawFieldType(Flipbook, Field, EJson::String))
            {
                AddReason(TEXT("flipbook_record_invalid"));
                break;
            }
        }
        for (const TCHAR* Field : {
                 TEXT("Columns"),
                 TEXT("Rows"),
                 TEXT("FrameCount"),
                 TEXT("StartFrame"),
                 TEXT("StaticFrameOverride")})
        {
            if (!HasRawIntegerField(Flipbook, Field))
            {
                AddReason(TEXT("flipbook_integer_field_invalid"));
                break;
            }
        }
        if (!HasRawFieldType(
                Flipbook,
                TEXT("FramesPerSecond"),
                EJson::Number))
        {
            AddReason(TEXT("flipbook_fps_out_of_range"));
        }
        if (!HasRawFieldType(Flipbook, TEXT("Loop"), EJson::Boolean))
        {
            AddReason(TEXT("flipbook_loop_invalid"));
        }
        if (!HasRawFieldType(Flipbook, TEXT("Phase"), EJson::Number))
        {
            AddReason(TEXT("flipbook_phase_out_of_range"));
        }
    }
    return Reasons;
}

TArray<FString> ValidateRawMaterializedBakedLayers(
    const TSharedPtr<FJsonObject>& DocumentObject,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    if (SchemaVersion < 13)
    {
        return Reasons;
    }
    const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
    if (!DocumentObject
        || !DocumentObject->TryGetArrayField(TEXT("Layers"), Layers)
        || !Layers)
    {
        return Reasons;
    }
    for (const TSharedPtr<FJsonValue>& LayerValue : *Layers)
    {
        const TSharedPtr<FJsonObject> Layer =
            LayerValue && LayerValue->Type == EJson::Object
            ? LayerValue->AsObject()
            : nullptr;
        if (!Layer)
        {
            continue;
        }
        FString Disposition;
        Layer->TryGetStringField(TEXT("Disposition"), Disposition);
        if (Disposition != TEXT("Baked"))
        {
            continue;
        }
        FString LayerId = TEXT("<unknown>");
        Layer->TryGetStringField(TEXT("Id"), LayerId);
        const auto AddReason = [&Reasons, &LayerId](const TCHAR* Reason)
        {
            Reasons.AddUnique(LayerId + TEXT(":") + Reason);
        };
        FString Kind;
        Layer->TryGetStringField(TEXT("Kind"), Kind);
        if (Kind != TEXT("Image"))
        {
            AddReason(TEXT("baked_static_vector_layer_kind_unsupported"));
        }
        const TSharedPtr<FJsonObject> ImageFill = RawObjectField(
            Layer,
            TEXT("ImageFill"));
        if (!ImageFill || ImageFill->Values.IsEmpty())
        {
            AddReason(TEXT("baked_image_fill_contract_invalid"));
        }
        const TSharedPtr<FJsonObject> Material = RawObjectField(
            Layer,
            TEXT("Material"));
        const TSharedPtr<FJsonObject> Flipbook = RawObjectField(
            Layer,
            TEXT("Flipbook"));
        if ((Material && !Material->Values.IsEmpty())
            || (Flipbook && !Flipbook->Values.IsEmpty()))
        {
            AddReason(TEXT("baked_conflicting_visual_record"));
        }
        const TArray<TSharedPtr<FJsonValue>>* BlockReasons = nullptr;
        if (!Layer->TryGetArrayField(TEXT("BlockReasons"), BlockReasons)
            || !BlockReasons
            || !BlockReasons->IsEmpty())
        {
            AddReason(TEXT("baked_block_reasons_must_be_empty"));
        }
        if (!HasRawFieldType(Layer, TEXT("PayloadJson"), EJson::String))
        {
            AddReason(TEXT("baked_payload_json_invalid"));
        }
        else
        {
            FString PayloadText;
            Layer->TryGetStringField(TEXT("PayloadJson"), PayloadText);
            TSharedPtr<FJsonObject> Payload;
            const TSharedRef<TJsonReader<>> PayloadReader =
                TJsonReaderFactory<>::Create(PayloadText);
            FString Mapping;
            FString Conversion;
            const TSharedPtr<FJsonObject>* PayloadImageFill = nullptr;
            const bool bPayloadParsed =
                FJsonSerializer::Deserialize(PayloadReader, Payload)
                && Payload
                && Payload->TryGetStringField(
                    TEXT("umg_mapping"),
                    Mapping)
                && Payload->TryGetStringField(
                    TEXT("painter_conversion"),
                    Conversion);
            const bool bStaticVectorMapping = bPayloadParsed
                && Mapping
                    == TEXT("texture2d_image_fill_from_static_vector_bake")
                && Conversion == TEXT("static_vector_png_bake");
            const bool bStaticAppearanceMapping = bPayloadParsed
                && Mapping
                    == TEXT(
                        "texture2d_image_fill_from_static_appearance_bake")
                && Conversion == TEXT("static_appearance_png_bake");
            const bool bStaticTextureMapping = bPayloadParsed
                && Mapping
                    == TEXT(
                        "texture2d_image_fill_from_static_texture_bake")
                && Conversion == TEXT("static_texture_png_bake");
            if (bStaticAppearanceMapping
                && SchemaVersion < StaticAppearanceBakeSchemaVersion)
            {
                AddReason(TEXT("static_appearance_bake_requires_schema_14"));
            }
            if (bStaticTextureMapping
                && SchemaVersion < StaticTextureBakeSchemaVersion)
            {
                AddReason(TEXT("static_texture_bake_requires_schema_15"));
            }
            if (bStaticAppearanceMapping || bStaticTextureMapping)
            {
                const TSharedPtr<FJsonObject> Bake = RawObjectField(
                    Payload,
                    TEXT("static_appearance_bake"));
                const TSharedPtr<FJsonObject> Source = RawObjectField(
                    Bake,
                    TEXT("source"));
                const TSharedPtr<FJsonObject> Effect = RawObjectField(
                    Source,
                    TEXT("effect"));
                FString AppearanceKind;
                FString SourceSchema;
                FString EffectType;
                FString SatisfiedGate;
                FString IntendedGate;
                FString SourceIntendedGate;
                if (Bake)
                {
                    Bake->TryGetStringField(
                        TEXT("kind"),
                        AppearanceKind);
                    Bake->TryGetStringField(
                        TEXT("satisfied_gate"),
                        SatisfiedGate);
                    Bake->TryGetStringField(
                        TEXT("intended_gate"),
                        IntendedGate);
                }
                if (Source)
                {
                    Source->TryGetStringField(
                        TEXT("schema"),
                        SourceSchema);
                    Source->TryGetStringField(
                        TEXT("intended_gate"),
                        SourceIntendedGate);
                }
                if (Effect)
                {
                    Effect->TryGetStringField(TEXT("type"), EffectType);
                }
                const bool bNoiseContract = bStaticAppearanceMapping
                    && AppearanceKind == StaticAppearanceBakeKind
                    && SourceSchema == StaticAppearanceBakeSchema
                    && EffectType == TEXT("noise")
                    && SatisfiedGate == StaticAppearanceBakeGate
                    && Bake
                    && !Bake->HasField(TEXT("intended_gate"))
                    && Source
                    && !Source->HasField(TEXT("intended_gate"));
                const bool bTextureContract = bStaticTextureMapping
                    && AppearanceKind == StaticTextureBakeKind
                    && SourceSchema == StaticTextureBakeSchema
                    && EffectType == TEXT("texture")
                    && SatisfiedGate == StaticTextureBakeGate
                    && IntendedGate == StaticTextureBakeGate
                    && SourceIntendedGate == StaticTextureBakeGate;
                if (!bNoiseContract && !bTextureContract)
                {
                    AddReason(
                        TEXT("baked_static_appearance_contract_mismatch"));
                }
            }
            if ((!bStaticVectorMapping
                    && !bStaticAppearanceMapping
                    && !bStaticTextureMapping)
                || !Payload->TryGetObjectField(
                    TEXT("image_fill"),
                    PayloadImageFill)
                || !PayloadImageFill
                || !PayloadImageFill->IsValid()
                || !FJsonValue::CompareEqual(
                    FJsonValueObject(ImageFill),
                    FJsonValueObject(*PayloadImageFill)))
            {
                AddReason(TEXT("baked_payload_contract_invalid"));
            }
        }
        FString LayerAssetId;
        FString ImageAssetId;
        Layer->TryGetStringField(TEXT("AssetId"), LayerAssetId);
        if (ImageFill)
        {
            ImageFill->TryGetStringField(TEXT("AssetId"), ImageAssetId);
        }
        if (LayerAssetId.IsEmpty()
            || ImageAssetId.IsEmpty()
            || LayerAssetId != ImageAssetId)
        {
            AddReason(TEXT("baked_asset_id_mismatch"));
        }
    }
    return Reasons;
}

bool IsFiniteVector2D(const FVector2D& Value)
{
    return FMath::IsFinite(Value.X) && FMath::IsFinite(Value.Y);
}

bool IsValidMaterialColor(const FString& Value)
{
    if (Value.Len() != 9 || Value[0] != TEXT('#'))
    {
        return false;
    }
    for (int32 Index = 1; Index < Value.Len(); ++Index)
    {
        if (!FChar::IsHexDigit(Value[Index]))
        {
            return false;
        }
    }
    return true;
}

void ValidateGradientStops(
    const FTigerStudioUMGMaterialRecord& Material,
    TArray<FString>& Reasons)
{
    if (Material.Stops.Num() < 2)
    {
        Reasons.Add(TEXT("ui_material_gradient_requires_two_stops"));
        return;
    }
    if (Material.Stops.Num() > 16)
    {
        Reasons.Add(TEXT("ui_material_gradient_stop_limit_exceeded"));
        return;
    }

    double PreviousPosition = -1.0;
    for (const FTigerStudioUMGGradientStopRecord& Stop : Material.Stops)
    {
        if (!FMath::IsFinite(Stop.Position)
            || Stop.Position < 0.0
            || Stop.Position > 1.0
            || !IsValidMaterialColor(Stop.Color))
        {
            Reasons.Add(TEXT("ui_material_gradient_stop_invalid"));
            break;
        }
        if (Stop.Position < PreviousPosition)
        {
            Reasons.Add(TEXT("ui_material_gradient_stops_not_sorted"));
            break;
        }
        PreviousPosition = Stop.Position;
    }
}

bool IsValidShadow(
    const FTigerStudioUMGShadowRecord& Shadow)
{
    return IsValidMaterialColor(Shadow.Color)
        && IsFiniteVector2D(Shadow.Offset)
        && FMath::IsFinite(Shadow.Blur)
        && Shadow.Blur >= 0.0
        && FMath::IsFinite(Shadow.Spread);
}

FMargin ExpectedVisualPadding(
    const FTigerStudioUMGStrokeRecord& Stroke,
    const FTigerStudioUMGShadowRecord& DropShadow)
{
    const double OutsideStroke = Stroke.Alignment == TEXT("Outside")
        ? Stroke.Width
        : Stroke.Alignment == TEXT("Center") ? Stroke.Width * 0.5 : 0.0;
    double Extent = 0.0;
    double OffsetX = 0.0;
    double OffsetY = 0.0;
    if (DropShadow.Enabled)
    {
        Extent = FMath::Max(0.0, DropShadow.Blur + DropShadow.Spread);
        OffsetX = DropShadow.Offset.X;
        OffsetY = DropShadow.Offset.Y;
    }
    return FMargin(
        OutsideStroke + FMath::Max(0.0, Extent - OffsetX),
        OutsideStroke + FMath::Max(0.0, Extent - OffsetY),
        OutsideStroke + FMath::Max(0.0, Extent + OffsetX),
        OutsideStroke + FMath::Max(0.0, Extent + OffsetY));
}

bool RoundedCardRequiresDynamicSizeBinding(
    const FTigerStudioUMGLayerRecord& Layer,
    const TMap<FString, FString>& ParentPanelKinds,
    const TSet<FString>& SyntheticOverlayRootIds = TSet<FString>())
{
    const bool bSyntheticOverlay = SyntheticOverlayRootIds.Contains(Layer.Id);
    if (!bSyntheticOverlay
        && !Layer.CanvasSlot.AnchorMinimum.Equals(
            Layer.CanvasSlot.AnchorMaximum,
            0.000001))
    {
        return true;
    }
    const FString ParentPanelKind = bSyntheticOverlay
        ? FString(TEXT("Overlay"))
        : ParentPanelKinds.FindRef(Layer.ParentId);
    if (ParentPanelKind.IsEmpty())
    {
        return false;
    }
    const bool bHorizontalFill = Layer.FlowSlot.HorizontalAlignment.Equals(
        TEXT("Fill"),
        ESearchCase::IgnoreCase);
    const bool bVerticalFill = Layer.FlowSlot.VerticalAlignment.Equals(
        TEXT("Fill"),
        ESearchCase::IgnoreCase);
    const bool bMainAxisFill = Layer.FlowSlot.SizeRule.Equals(
        TEXT("Fill"),
        ESearchCase::IgnoreCase);
    if (ParentPanelKind == TEXT("Horizontal"))
    {
        return (bMainAxisFill && bHorizontalFill) || bVerticalFill;
    }
    if (ParentPanelKind == TEXT("Vertical"))
    {
        return (bMainAxisFill && bVerticalFill) || bHorizontalFill;
    }
    return (ParentPanelKind == TEXT("Grid")
            || ParentPanelKind == TEXT("Overlay"))
        && (bHorizontalFill || bVerticalFill);
}

bool HasImageFillCornerRadii(const FVector4& Radii)
{
    return Radii.X > 0.0001
        || Radii.Y > 0.0001
        || Radii.Z > 0.0001
        || Radii.W > 0.0001;
}

bool HasUnsupportedImageAdjustments(
    const FTigerStudioUMGImageAdjustmentsRecord& Adjustments)
{
    const double Values[] = {
        Adjustments.Exposure,
        Adjustments.Contrast,
        Adjustments.Saturation,
        Adjustments.Temperature,
        Adjustments.Tint,
        Adjustments.Highlights,
    };
    for (const double Value : Values)
    {
        if (!FMath::IsFinite(Value) || !FMath::IsNearlyZero(Value, 0.0001))
        {
            return true;
        }
    }
    return false;
}

TArray<FString> ValidateImageFillLayer(
    const FTigerStudioUMGLayerRecord& Layer,
    const int32 SchemaVersion,
    const TMap<FString, FString>& ResourceKinds,
    const TMap<FString, FString>& ParentPanelKinds,
    const TSet<FString>& SyntheticOverlayRootIds = TSet<FString>())
{
    TArray<FString> Reasons;
    const FTigerStudioUMGImageFillRecord& ImageFill = Layer.ImageFill;
    if (ImageFill.AssetId.IsEmpty())
    {
        return Reasons;
    }

    if (SchemaVersion < 11)
    {
        Reasons.Add(TEXT("image_fill_requires_schema_11"));
    }
    if (Layer.Kind != ETigerStudioUMGLayerKind::Group
        && Layer.Kind != ETigerStudioUMGLayerKind::Shape
        && Layer.Kind != ETigerStudioUMGLayerKind::Image
        && Layer.Kind != ETigerStudioUMGLayerKind::Button)
    {
        Reasons.Add(TEXT("image_fill_layer_kind_unsupported"));
    }
    if (!Layer.AssetId.IsEmpty() && Layer.AssetId != ImageFill.AssetId)
    {
        Reasons.Add(TEXT("image_fill_asset_id_mismatch"));
    }
    const FString* ResourceKind = ResourceKinds.Find(ImageFill.AssetId);
    if (!ResourceKind)
    {
        Reasons.Add(TEXT("image_fill_resource_missing"));
    }
    else if (!ResourceKind->Equals(TEXT("texture"), ESearchCase::IgnoreCase)
        && !ResourceKind->Equals(TEXT("image"), ESearchCase::IgnoreCase))
    {
        Reasons.Add(TEXT("image_fill_resource_kind_unsupported"));
    }

    const bool bStretch = ImageFill.Mode == TEXT("Stretch");
    const bool bFit = ImageFill.Mode == TEXT("Fit");
    const bool bFill = ImageFill.Mode == TEXT("Fill");
    const bool bCrop = ImageFill.Mode == TEXT("Crop");
    const bool bTile = ImageFill.Mode == TEXT("Tile");
    if (!bStretch && !bFit && !bFill && !bCrop && !bTile)
    {
        Reasons.Add(
            TEXT("image_fill_mode_unsupported:")
            + (ImageFill.Mode.IsEmpty() ? TEXT("empty") : ImageFill.Mode));
    }

    if (!IsFiniteVector2D(ImageFill.SourceSize)
        || ImageFill.SourceSize.X < 0.0
        || ImageFill.SourceSize.Y < 0.0
        || ((ImageFill.SourceSize.X <= 0.0)
            != (ImageFill.SourceSize.Y <= 0.0)))
    {
        Reasons.Add(TEXT("image_fill_source_size_invalid"));
    }
    if (!IsFiniteVector2D(ImageFill.FocalPoint)
        || ImageFill.FocalPoint.X < 0.0
        || ImageFill.FocalPoint.X > 1.0
        || ImageFill.FocalPoint.Y < 0.0
        || ImageFill.FocalPoint.Y > 1.0)
    {
        Reasons.Add(TEXT("image_fill_focal_point_invalid"));
    }
    if (!FMath::IsFinite(ImageFill.TileScale)
        || ImageFill.TileScale <= 0.0)
    {
        Reasons.Add(TEXT("image_fill_tile_scale_invalid"));
    }
    if (!FMath::IsFinite(ImageFill.Opacity)
        || ImageFill.Opacity < 0.0
        || ImageFill.Opacity > 1.0)
    {
        Reasons.Add(TEXT("image_fill_opacity_invalid"));
    }
    if (!IsValidMaterialColor(ImageFill.Tint))
    {
        Reasons.Add(TEXT("image_fill_tint_invalid"));
    }
    if (HasUnsupportedImageAdjustments(ImageFill.Adjustments))
    {
        Reasons.Add(
            TEXT("image_fill_adjustments_require_ui_material_or_bake"));
    }

    const FTigerStudioUMGImageCropRecord& Crop = ImageFill.Crop;
    if (bCrop && !Crop.Enabled)
    {
        Reasons.Add(TEXT("image_fill_crop_rect_missing"));
    }
    if (Crop.Enabled)
    {
        const bool bNormalized = Crop.Units == TEXT("Normalized");
        const bool bPixels = Crop.Units == TEXT("Pixels");
        if (!bNormalized && !bPixels)
        {
            Reasons.Add(TEXT("image_fill_crop_units_invalid"));
        }
        const bool bFiniteRect = FMath::IsFinite(Crop.X)
            && FMath::IsFinite(Crop.Y)
            && FMath::IsFinite(Crop.Width)
            && FMath::IsFinite(Crop.Height);
        if (!bFiniteRect
            || Crop.X < 0.0
            || Crop.Y < 0.0
            || Crop.Width <= 0.0
            || Crop.Height <= 0.0)
        {
            Reasons.Add(TEXT("image_fill_crop_rect_invalid"));
        }
        else if ((bNormalized
                    && (Crop.X + Crop.Width > 1.000001
                        || Crop.Y + Crop.Height > 1.000001))
            || (bPixels
                && ImageFill.SourceSize.X > 0.0
                && ImageFill.SourceSize.Y > 0.0
                && (Crop.X + Crop.Width > ImageFill.SourceSize.X + 0.0001
                    || Crop.Y + Crop.Height
                        > ImageFill.SourceSize.Y + 0.0001)))
        {
            Reasons.Add(TEXT("image_fill_crop_rect_out_of_bounds"));
        }
    }

    const FVector4& Radii = ImageFill.CornerRadii;
    if (!FMath::IsFinite(Radii.X)
        || !FMath::IsFinite(Radii.Y)
        || !FMath::IsFinite(Radii.Z)
        || !FMath::IsFinite(Radii.W)
        || Radii.X < 0.0
        || Radii.Y < 0.0
        || Radii.Z < 0.0
        || Radii.W < 0.0
        || Layer.Size.X <= 0.0
        || Layer.Size.Y <= 0.0
        || Radii.X + Radii.Y > Layer.Size.X + 0.0001
        || Radii.W + Radii.Z > Layer.Size.X + 0.0001
        || Radii.X + Radii.W > Layer.Size.Y + 0.0001
        || Radii.Y + Radii.Z > Layer.Size.Y + 0.0001)
    {
        Reasons.Add(TEXT("image_fill_corner_radii_invalid"));
    }

    const FTigerStudioUMGImageNineSliceRecord& NineSlice =
        ImageFill.NineSlice;
    if (NineSlice.Enabled)
    {
        FVector2D NineSliceSourceSize = ImageFill.SourceSize;
        if (Crop.Enabled)
        {
            if (Crop.Units == TEXT("Pixels"))
            {
                NineSliceSourceSize = FVector2D(
                    Crop.Width,
                    Crop.Height);
            }
            else if (Crop.Units == TEXT("Normalized")
                && ImageFill.SourceSize.X > 0.0
                && ImageFill.SourceSize.Y > 0.0)
            {
                NineSliceSourceSize = FVector2D(
                    ImageFill.SourceSize.X * Crop.Width,
                    ImageFill.SourceSize.Y * Crop.Height);
            }
        }
        if (!bStretch)
        {
            Reasons.Add(TEXT("image_fill_nine_slice_requires_stretch"));
        }
        if (HasImageFillCornerRadii(Radii))
        {
            Reasons.Add(
                TEXT(
                    "image_fill_nine_slice_rounded_corners_require_ui_material_or_bake"));
        }
        const bool bPixels = NineSlice.Units == TEXT("Pixels");
        if (!bPixels)
        {
            Reasons.Add(TEXT("image_fill_nine_slice_units_invalid"));
        }
        const bool bFiniteMargins = FMath::IsFinite(NineSlice.Left)
            && FMath::IsFinite(NineSlice.Top)
            && FMath::IsFinite(NineSlice.Right)
            && FMath::IsFinite(NineSlice.Bottom);
        if (!bFiniteMargins
            || NineSlice.Left < 0.0
            || NineSlice.Top < 0.0
            || NineSlice.Right < 0.0
            || NineSlice.Bottom < 0.0)
        {
            Reasons.Add(TEXT("image_fill_nine_slice_margins_invalid"));
        }
        else if (bPixels
                && NineSliceSourceSize.X > 0.0
                && NineSliceSourceSize.Y > 0.0
                && (NineSlice.Left + NineSlice.Right
                        >= NineSliceSourceSize.X
                    || NineSlice.Top + NineSlice.Bottom
                        >= NineSliceSourceSize.Y))
        {
            Reasons.Add(TEXT("image_fill_nine_slice_margins_out_of_bounds"));
        }
    }
    if (bTile && HasImageFillCornerRadii(Radii))
    {
        Reasons.Add(
            TEXT("image_fill_tile_rounded_corners_require_ui_material_or_bake"));
    }
    if (bFill && RoundedCardRequiresDynamicSizeBinding(
            Layer,
            ParentPanelKinds,
            SyntheticOverlayRootIds))
    {
        Reasons.Add(
            TEXT("image_fill_runtime_resize_requires_dynamic_uv_binding"));
    }
    return Reasons;
}

bool IsSha256Hex(const FString& Value)
{
    if (Value.Len() != 64)
    {
        return false;
    }
    for (const TCHAR Character : Value)
    {
        if (!FChar::IsHexDigit(Character))
        {
            return false;
        }
    }
    return true;
}

int32 StaticVectorCommandArity(const TCHAR Command)
{
    switch (FChar::ToUpper(Command))
    {
    case TEXT('M'):
    case TEXT('L'):
    case TEXT('T'):
        return 2;
    case TEXT('H'):
    case TEXT('V'):
        return 1;
    case TEXT('C'):
        return 6;
    case TEXT('S'):
    case TEXT('Q'):
        return 4;
    case TEXT('A'):
        return 7;
    default:
        return 0;
    }
}

bool ValidateStaticVectorPathSyntax(
    const FString& Path,
    int32& OutSubpathCount,
    int32& OutTokenCount)
{
    FString Trimmed = Path;
    Trimmed.TrimStartAndEndInline();
    if (Trimmed.IsEmpty()
        || Trimmed.StartsWith(TEXT(","))
        || Trimmed.EndsWith(TEXT(",")))
    {
        return false;
    }
    for (int32 Index = 0; Index < Trimmed.Len(); ++Index)
    {
        if (Trimmed[Index] != TEXT(','))
        {
            continue;
        }
        int32 Before = Index - 1;
        int32 After = Index + 1;
        while (Before >= 0 && FChar::IsWhitespace(Trimmed[Before]))
        {
            --Before;
        }
        while (After < Trimmed.Len() && FChar::IsWhitespace(Trimmed[After]))
        {
            ++After;
        }
        if (Before < 0
            || After >= Trimmed.Len()
            || FChar::IsAlpha(Trimmed[Before])
            || Trimmed[After] == TEXT(',')
            || FChar::IsAlpha(Trimmed[After]))
        {
            return false;
        }
    }

    TArray<FString> Tokens;
    int32 Index = 0;
    while (Index < Trimmed.Len())
    {
        const TCHAR Character = Trimmed[Index];
        if (Character > 127 && FChar::IsWhitespace(Character))
        {
            return false;
        }
        if (FChar::IsWhitespace(Character) || Character == TEXT(','))
        {
            ++Index;
            continue;
        }
        if (FChar::IsAlpha(Character))
        {
            Tokens.Add(FString::Chr(Character));
            ++Index;
        }
        else
        {
            const int32 StartIndex = Index;
            if (Trimmed[Index] == TEXT('+') || Trimmed[Index] == TEXT('-'))
            {
                ++Index;
            }
            bool bHasDigit = false;
            while (Index < Trimmed.Len() && FChar::IsDigit(Trimmed[Index]))
            {
                bHasDigit = true;
                ++Index;
            }
            if (Index < Trimmed.Len() && Trimmed[Index] == TEXT('.'))
            {
                ++Index;
                while (Index < Trimmed.Len() && FChar::IsDigit(Trimmed[Index]))
                {
                    bHasDigit = true;
                    ++Index;
                }
            }
            if (!bHasDigit)
            {
                return false;
            }
            if (Index < Trimmed.Len()
                && (Trimmed[Index] == TEXT('e') || Trimmed[Index] == TEXT('E')))
            {
                ++Index;
                if (Index < Trimmed.Len()
                    && (Trimmed[Index] == TEXT('+')
                        || Trimmed[Index] == TEXT('-')))
                {
                    ++Index;
                }
                const int32 ExponentStart = Index;
                while (Index < Trimmed.Len() && FChar::IsDigit(Trimmed[Index]))
                {
                    ++Index;
                }
                if (Index == ExponentStart)
                {
                    return false;
                }
            }
            const FString NumberToken = Trimmed.Mid(
                StartIndex,
                Index - StartIndex);
            if (!FMath::IsFinite(FCString::Atod(*NumberToken)))
            {
                return false;
            }
            Tokens.Add(NumberToken);
        }
        if (Tokens.Num() > 100000)
        {
            return false;
        }
    }
    OutTokenCount = Tokens.Num();
    OutSubpathCount = 0;
    FString CurrentCommand;
    bool bOpenSubpath = false;
    bool bSawMove = false;
    int32 TokenIndex = 0;
    while (TokenIndex < Tokens.Num())
    {
        const FString& Token = Tokens[TokenIndex];
        if (Token.Len() == 1 && FChar::IsAlpha(Token[0]))
        {
            CurrentCommand = Token;
            ++TokenIndex;
            const TCHAR UpperCommand = FChar::ToUpper(CurrentCommand[0]);
            if (UpperCommand == TEXT('Z'))
            {
                if (!bOpenSubpath)
                {
                    return false;
                }
                bOpenSubpath = false;
                ++OutSubpathCount;
                CurrentCommand.Reset();
                continue;
            }
            if (StaticVectorCommandArity(CurrentCommand[0]) == 0)
            {
                return false;
            }
            if (UpperCommand == TEXT('M'))
            {
                if (bOpenSubpath)
                {
                    return false;
                }
                if (bSawMove && CurrentCommand[0] == TEXT('m'))
                {
                    return false;
                }
                bOpenSubpath = true;
                bSawMove = true;
            }
            else if (!bOpenSubpath)
            {
                return false;
            }
        }
        else if (CurrentCommand.IsEmpty())
        {
            return false;
        }

        const int32 Arity = StaticVectorCommandArity(CurrentCommand[0]);
        int32 EndIndex = TokenIndex;
        while (EndIndex < Tokens.Num()
            && !(Tokens[EndIndex].Len() == 1
                && FChar::IsAlpha(Tokens[EndIndex][0])))
        {
            ++EndIndex;
        }
        const int32 ParameterCount = EndIndex - TokenIndex;
        if (ParameterCount <= 0 || ParameterCount % Arity != 0)
        {
            return false;
        }
        if (FChar::ToUpper(CurrentCommand[0]) == TEXT('A'))
        {
            for (int32 Group = TokenIndex; Group < EndIndex; Group += Arity)
            {
                const double RadiusX = FCString::Atod(*Tokens[Group]);
                const double RadiusY = FCString::Atod(*Tokens[Group + 1]);
                if (RadiusX < 0.0
                    || RadiusY < 0.0
                    || (Tokens[Group + 3] != TEXT("0")
                        && Tokens[Group + 3] != TEXT("1"))
                    || (Tokens[Group + 4] != TEXT("0")
                        && Tokens[Group + 4] != TEXT("1")))
                {
                    return false;
                }
            }
        }
        TokenIndex = EndIndex;
    }
    return !bOpenSubpath && OutSubpathCount > 0;
}

bool IsEmptyMaterialRecord(const FTigerStudioUMGMaterialRecord& Material)
{
    return Material.Schema.IsEmpty()
        && Material.Generator.IsEmpty()
        && Material.Kind.IsEmpty()
        && Material.CoordinateSpace.IsEmpty()
        && Material.Stops.IsEmpty();
}

bool IsEmptyFlipbookRecord(const FTigerStudioUMGFlipbookRecord& Flipbook)
{
    return Flipbook.Schema.IsEmpty()
        && Flipbook.Generator.IsEmpty()
        && Flipbook.Kind.IsEmpty()
        && Flipbook.CoordinateSpace.IsEmpty()
        && Flipbook.AssetId.IsEmpty();
}

bool IsEmptyButtonStyleRecord(
    const FTigerStudioUMGButtonStyleRecord& ButtonStyle)
{
    // Empty JSON objects deserialize nested state defaults, so Schema is the
    // record-presence discriminator used for schema 4-15 compatibility.
    return ButtonStyle.Schema.IsEmpty();
}

void ValidateButtonStateRecord(
    const FTigerStudioUMGButtonStateRecord& State,
    const FString& Prefix,
    TArray<FString>& Reasons)
{
    if (!IsValidMaterialColor(State.Fill))
    {
        Reasons.Add(Prefix + TEXT("_fill_invalid"));
    }
    if (!IsValidMaterialColor(State.Stroke))
    {
        Reasons.Add(Prefix + TEXT("_stroke_invalid"));
    }
    if (!FMath::IsFinite(State.StrokeWidth)
        || State.StrokeWidth < 0.0
        || State.StrokeWidth > 1024.0)
    {
        Reasons.Add(Prefix + TEXT("_stroke_width_invalid"));
    }
    if (!FMath::IsFinite(State.CornerRadii.X)
        || !FMath::IsFinite(State.CornerRadii.Y)
        || !FMath::IsFinite(State.CornerRadii.Z)
        || !FMath::IsFinite(State.CornerRadii.W)
        || State.CornerRadii.X < 0.0
        || State.CornerRadii.Y < 0.0
        || State.CornerRadii.Z < 0.0
        || State.CornerRadii.W < 0.0
        || State.CornerRadii.X > 8192.0
        || State.CornerRadii.Y > 8192.0
        || State.CornerRadii.Z > 8192.0
        || State.CornerRadii.W > 8192.0)
    {
        Reasons.Add(Prefix + TEXT("_corner_radii_invalid"));
    }
    if (!IsValidMaterialColor(State.TextColor))
    {
        Reasons.Add(Prefix + TEXT("_text_color_invalid"));
    }
    if (!FMath::IsFinite(State.FontSize)
        || State.FontSize < 1.0
        || State.FontSize > 512.0)
    {
        Reasons.Add(Prefix + TEXT("_font_size_invalid"));
    }
    if (State.FontWeight < 100 || State.FontWeight > 900)
    {
        Reasons.Add(Prefix + TEXT("_font_weight_invalid"));
    }
    if (!FMath::IsFinite(State.Opacity)
        || State.Opacity < 0.0
        || State.Opacity > 1.0)
    {
        Reasons.Add(Prefix + TEXT("_opacity_invalid"));
    }
}

TArray<FString> ValidateButtonStyleLayer(
    const FTigerStudioUMGLayerRecord& Layer,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    if (HasValidComponentInstancePayload(Layer))
    {
        return Reasons;
    }
    const FTigerStudioUMGButtonStyleRecord& ButtonStyle =
        Layer.ButtonStyle;
    const bool bEmpty = IsEmptyButtonStyleRecord(ButtonStyle);
    if (bEmpty)
    {
        if (SchemaVersion >= ButtonStyleSchemaVersion
            && Layer.Kind == ETigerStudioUMGLayerKind::Button
            && Layer.Disposition == ETigerStudioUMGDisposition::Native)
        {
            Reasons.Add(TEXT("button_style_missing"));
        }
        return Reasons;
    }
    if (SchemaVersion < ButtonStyleSchemaVersion)
    {
        Reasons.Add(TEXT("button_style_requires_schema_16"));
        return Reasons;
    }
    if (Layer.Kind != ETigerStudioUMGLayerKind::Button)
    {
        Reasons.Add(TEXT("button_style_layer_kind_unsupported"));
        return Reasons;
    }
    if (Layer.Disposition != ETigerStudioUMGDisposition::Native)
    {
        Reasons.Add(TEXT("button_style_requires_native_disposition"));
    }
    if (ButtonStyle.Schema != ButtonStyleSchema)
    {
        Reasons.Add(TEXT("button_style_schema_unsupported"));
    }

    ValidateButtonStateRecord(
        ButtonStyle.Normal,
        TEXT("button_style_normal"),
        Reasons);
    ValidateButtonStateRecord(
        ButtonStyle.Hovered,
        TEXT("button_style_hovered"),
        Reasons);
    ValidateButtonStateRecord(
        ButtonStyle.Pressed,
        TEXT("button_style_pressed"),
        Reasons);
    ValidateButtonStateRecord(
        ButtonStyle.Disabled,
        TEXT("button_style_disabled"),
        Reasons);

    const auto MatchesNormalFont = [&ButtonStyle](
        const FTigerStudioUMGButtonStateRecord& State)
    {
        return FMath::IsNearlyEqual(
                State.FontSize,
                ButtonStyle.Normal.FontSize,
                0.000001)
            && State.FontWeight == ButtonStyle.Normal.FontWeight;
    };
    if (!MatchesNormalFont(ButtonStyle.Hovered)
        || !MatchesNormalFont(ButtonStyle.Pressed)
        || !MatchesNormalFont(ButtonStyle.Disabled))
    {
        // Native SButton changes foreground and brushes per state but its
        // child text style has one font.  Reject variation until a runtime
        // binding exists instead of flattening it to Normal.
        Reasons.Add(
            TEXT("button_style_state_font_metrics_require_runtime_binding"));
    }
    return Reasons;
}

bool HasExactFields(
    const TSharedPtr<FJsonObject>& Object,
    const std::initializer_list<const TCHAR*> Fields)
{
    if (!Object || Object->Values.Num() != static_cast<int32>(Fields.size()))
    {
        return false;
    }
    for (const TCHAR* Field : Fields)
    {
        if (!Object->HasField(Field))
        {
            return false;
        }
    }
    return true;
}

bool TryGetFiniteNumber(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field,
    double& OutValue)
{
    return Object
        && Object->TryGetNumberField(Field, OutValue)
        && FMath::IsFinite(OutValue);
}

bool JsonVectorEquals(
    const TSharedPtr<FJsonObject>& Object,
    const FVector2D& Expected)
{
    double X = 0.0;
    double Y = 0.0;
    return HasExactFields(Object, {TEXT("X"), TEXT("Y")})
        && TryGetFiniteNumber(Object, TEXT("X"), X)
        && TryGetFiniteNumber(Object, TEXT("Y"), Y)
        && FMath::IsNearlyEqual(X, Expected.X, 0.000001)
        && FMath::IsNearlyEqual(Y, Expected.Y, 0.000001);
}

bool JsonMarginEquals(
    const TSharedPtr<FJsonObject>& Object,
    const FMargin& Expected)
{
    double Left = 0.0;
    double Top = 0.0;
    double Right = 0.0;
    double Bottom = 0.0;
    return HasExactFields(
            Object,
            {TEXT("Left"), TEXT("Top"), TEXT("Right"), TEXT("Bottom")})
        && TryGetFiniteNumber(Object, TEXT("Left"), Left)
        && TryGetFiniteNumber(Object, TEXT("Top"), Top)
        && TryGetFiniteNumber(Object, TEXT("Right"), Right)
        && TryGetFiniteNumber(Object, TEXT("Bottom"), Bottom)
        && FMath::IsNearlyEqual(Left, Expected.Left, 0.000001)
        && FMath::IsNearlyEqual(Top, Expected.Top, 0.000001)
        && FMath::IsNearlyEqual(Right, Expected.Right, 0.000001)
        && FMath::IsNearlyEqual(Bottom, Expected.Bottom, 0.000001);
}

bool JsonCanvasSlotEquals(
    const TSharedPtr<FJsonObject>& Object,
    const FTigerStudioUMGCanvasSlotRecord& Expected)
{
    return HasExactFields(
            Object,
            {TEXT("AnchorMinimum"),
             TEXT("AnchorMaximum"),
             TEXT("Offsets"),
             TEXT("Alignment")})
        && JsonVectorEquals(
            RawObjectField(Object, TEXT("AnchorMinimum")),
            Expected.AnchorMinimum)
        && JsonVectorEquals(
            RawObjectField(Object, TEXT("AnchorMaximum")),
            Expected.AnchorMaximum)
        && JsonMarginEquals(
            RawObjectField(Object, TEXT("Offsets")),
            Expected.Offsets)
        && JsonVectorEquals(
            RawObjectField(Object, TEXT("Alignment")),
            Expected.Alignment);
}

bool CanonicalJsonObjectMatches(
    const FString& CanonicalJson,
    const TSharedPtr<FJsonObject>& ExpectedObject,
    const FString& ExpectedHash)
{
    if (CanonicalJson.IsEmpty()
        || !ExpectedObject
        || !IsSha256Hex(ExpectedHash))
    {
        return false;
    }
    FString ActualHash;
    if (!HashUtf8Sha256(CanonicalJson, ActualHash)
        || !ActualHash.Equals(ExpectedHash, ESearchCase::IgnoreCase))
    {
        return false;
    }
    TSharedPtr<FJsonObject> ParsedObject;
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(CanonicalJson);
    return FJsonSerializer::Deserialize(Reader, ParsedObject)
        && ParsedObject
        && FJsonValue::CompareEqual(
            FJsonValueObject(ExpectedObject),
            FJsonValueObject(ParsedObject));
}

bool JsonStringArrayEquals(
    const TSharedPtr<FJsonObject>& Object,
    const TCHAR* Field,
    const std::initializer_list<const TCHAR*> Expected)
{
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Object
        || !Object->TryGetArrayField(Field, Values)
        || !Values
        || Values->Num() != static_cast<int32>(Expected.size()))
    {
        return false;
    }
    int32 Index = 0;
    for (const TCHAR* ExpectedValue : Expected)
    {
        const TSharedPtr<FJsonValue>& Value = (*Values)[Index++];
        if (!Value
            || Value->Type != EJson::String
            || Value->AsString() != ExpectedValue)
        {
            return false;
        }
    }
    return true;
}

bool IsSupportedAppearanceBlendMode(const FString& Value)
{
    return Value == TEXT("normal")
        || Value == TEXT("darken")
        || Value == TEXT("multiply")
        || Value == TEXT("color_burn")
        || Value == TEXT("lighten")
        || Value == TEXT("screen")
        || Value == TEXT("color_dodge")
        || Value == TEXT("overlay")
        || Value == TEXT("soft_light")
        || Value == TEXT("hard_light")
        || Value == TEXT("difference")
        || Value == TEXT("exclusion")
        || Value == TEXT("linear_burn")
        || Value == TEXT("linear_dodge")
        || Value == TEXT("hue")
        || Value == TEXT("saturation")
        || Value == TEXT("color")
        || Value == TEXT("luminosity");
}

bool IsUppercaseMaterialColor(const FString& Value)
{
    return IsValidMaterialColor(Value) && Value == Value.ToUpper();
}

bool ValidateStaticAppearanceEffect(
    const TSharedPtr<FJsonObject>& Effect)
{
    if (!Effect)
    {
        return false;
    }
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Effect->Values)
    {
        if (Pair.Key != TEXT("type")
            && Pair.Key != TEXT("color")
            && Pair.Key != TEXT("blend_mode")
            && Pair.Key != TEXT("noise_size")
            && Pair.Key != TEXT("noise_size_vector")
            && Pair.Key != TEXT("noise_type")
            && Pair.Key != TEXT("density")
            && Pair.Key != TEXT("secondary_color")
            && Pair.Key != TEXT("opacity"))
        {
            return false;
        }
    }
    FString Type;
    FString Color;
    FString BlendMode;
    FString NoiseType;
    double NoiseSize = 0.0;
    double Density = 0.0;
    if (!Effect->TryGetStringField(TEXT("type"), Type)
        || Type != TEXT("noise")
        || !Effect->TryGetStringField(TEXT("color"), Color)
        || !IsUppercaseMaterialColor(Color)
        || !Effect->TryGetStringField(TEXT("blend_mode"), BlendMode)
        || !IsSupportedAppearanceBlendMode(BlendMode)
        || !TryGetFiniteNumber(Effect, TEXT("noise_size"), NoiseSize)
        || NoiseSize < 0.0
        || !Effect->TryGetStringField(TEXT("noise_type"), NoiseType)
        || (NoiseType != TEXT("monotone")
            && NoiseType != TEXT("duotone")
            && NoiseType != TEXT("multitone"))
        || !TryGetFiniteNumber(Effect, TEXT("density"), Density)
        || Density < 0.0
        || Density > 1.0)
    {
        return false;
    }
    if (Effect->HasField(TEXT("noise_size_vector")))
    {
        const TSharedPtr<FJsonObject> Vector = RawObjectField(
            Effect,
            TEXT("noise_size_vector"));
        double X = 0.0;
        double Y = 0.0;
        if (!HasExactFields(Vector, {TEXT("x"), TEXT("y")})
            || !TryGetFiniteNumber(Vector, TEXT("x"), X)
            || !TryGetFiniteNumber(Vector, TEXT("y"), Y)
            || X < 0.0
            || Y < 0.0)
        {
            return false;
        }
    }
    if (Effect->HasField(TEXT("secondary_color")))
    {
        FString SecondaryColor;
        if (!Effect->TryGetStringField(
                TEXT("secondary_color"),
                SecondaryColor)
            || !IsUppercaseMaterialColor(SecondaryColor))
        {
            return false;
        }
    }
    if (Effect->HasField(TEXT("opacity")))
    {
        double Opacity = 0.0;
        if (!TryGetFiniteNumber(Effect, TEXT("opacity"), Opacity)
            || Opacity < 0.0
            || Opacity > 1.0)
        {
            return false;
        }
    }
    return true;
}

bool ValidateStaticTextureEffect(
    const TSharedPtr<FJsonObject>& Effect)
{
    if (!Effect)
    {
        return false;
    }
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Effect->Values)
    {
        if (Pair.Key != TEXT("type")
            && Pair.Key != TEXT("radius")
            && Pair.Key != TEXT("noise_size")
            && Pair.Key != TEXT("clip_to_shape")
            && Pair.Key != TEXT("noise_size_vector"))
        {
            return false;
        }
    }
    FString Type;
    double Radius = 0.0;
    double NoiseSize = 0.0;
    if (!Effect->TryGetStringField(TEXT("type"), Type)
        || Type != TEXT("texture")
        || !TryGetFiniteNumber(Effect, TEXT("radius"), Radius)
        || Radius < 0.0
        || !TryGetFiniteNumber(Effect, TEXT("noise_size"), NoiseSize)
        || NoiseSize < 0.0
        || !HasRawFieldType(
            Effect,
            TEXT("clip_to_shape"),
            EJson::Boolean))
    {
        return false;
    }
    if (Effect->HasField(TEXT("noise_size_vector")))
    {
        const TSharedPtr<FJsonObject> Vector = RawObjectField(
            Effect,
            TEXT("noise_size_vector"));
        double X = 0.0;
        double Y = 0.0;
        if (!HasExactFields(Vector, {TEXT("x"), TEXT("y")})
            || !TryGetFiniteNumber(Vector, TEXT("x"), X)
            || !TryGetFiniteNumber(Vector, TEXT("y"), Y)
            || X < 0.0
            || Y < 0.0)
        {
            return false;
        }
    }
    return true;
}

TArray<FString> ValidateMaterializedStaticAppearanceBake(
    const FTigerStudioUMGLayerRecord& Layer,
    const TSharedPtr<FJsonObject>& Bake,
    const FString& SourceHash,
    const FString& PixelHash,
    const TMap<FString, FString>& ResourceSourcePaths,
    const bool bStaticTextureBake)
{
    TArray<FString> Reasons;
    const TCHAR* ExpectedKind = bStaticTextureBake
        ? StaticTextureBakeKind
        : StaticAppearanceBakeKind;
    const TCHAR* ExpectedSchema = bStaticTextureBake
        ? StaticTextureBakeSchema
        : StaticAppearanceBakeSchema;
    const TCHAR* ExpectedGate = bStaticTextureBake
        ? StaticTextureBakeGate
        : StaticAppearanceBakeGate;
    const TCHAR* ExpectedIntegrationStatus = bStaticTextureBake
        ? TEXT("tigerstudio_umg_schema15_materialized")
        : TEXT("tigerstudio_umg_schema14_materialized");
    const bool bMaterializationFieldsValid = bStaticTextureBake
        ? HasExactFields(
            Bake,
            {TEXT("kind"),
             TEXT("status"),
             TEXT("available"),
             TEXT("reasons"),
             TEXT("source_hash"),
             TEXT("effect_hash"),
             TEXT("source_canonical_json"),
             TEXT("effect_canonical_json"),
             TEXT("content_hash"),
             TEXT("pixel_rgba_sha256"),
             TEXT("origin_disposition"),
             TEXT("satisfied_gate"),
             TEXT("gate_transition"),
             TEXT("source"),
             TEXT("provenance"),
             TEXT("manifest_path"),
             TEXT("manifest_sha256"),
             TEXT("png_path"),
             TEXT("layout_preservation"),
             TEXT("integration_status"),
             TEXT("intended_gate"),
             TEXT("umg_support_claimed")})
        : HasExactFields(
            Bake,
            {TEXT("kind"),
             TEXT("status"),
             TEXT("available"),
             TEXT("reasons"),
             TEXT("source_hash"),
             TEXT("effect_hash"),
             TEXT("source_canonical_json"),
             TEXT("effect_canonical_json"),
             TEXT("content_hash"),
             TEXT("pixel_rgba_sha256"),
             TEXT("origin_disposition"),
             TEXT("satisfied_gate"),
             TEXT("gate_transition"),
             TEXT("source"),
             TEXT("provenance"),
             TEXT("manifest_path"),
             TEXT("manifest_sha256"),
             TEXT("png_path"),
             TEXT("layout_preservation"),
             TEXT("integration_status"),
             TEXT("umg_support_claimed")});
    if (!bMaterializationFieldsValid)
    {
        Reasons.Add(
            TEXT("baked_static_appearance_materialization_record_invalid"));
    }
    FString Kind;
    FString EffectHash;
    FString SourceCanonicalJson;
    FString EffectCanonicalJson;
    FString ManifestHash;
    FString IntegrationStatus;
    FString IntendedGate;
    bool bUmgSupportClaimed = false;
    Bake->TryGetStringField(TEXT("kind"), Kind);
    Bake->TryGetStringField(TEXT("effect_hash"), EffectHash);
    Bake->TryGetStringField(
        TEXT("source_canonical_json"),
        SourceCanonicalJson);
    Bake->TryGetStringField(
        TEXT("effect_canonical_json"),
        EffectCanonicalJson);
    Bake->TryGetStringField(TEXT("manifest_sha256"), ManifestHash);
    Bake->TryGetStringField(TEXT("integration_status"), IntegrationStatus);
    Bake->TryGetStringField(TEXT("intended_gate"), IntendedGate);
    Bake->TryGetBoolField(TEXT("umg_support_claimed"), bUmgSupportClaimed);
    if (Kind != ExpectedKind)
    {
        Reasons.Add(TEXT("baked_static_appearance_kind_invalid"));
    }
    if ((bStaticTextureBake && IntendedGate != ExpectedGate)
        || (!bStaticTextureBake && Bake->HasField(TEXT("intended_gate"))))
    {
        Reasons.Add(
            TEXT("baked_static_appearance_intended_gate_invalid"));
    }
    if (!IsSha256Hex(EffectHash) || !IsSha256Hex(ManifestHash))
    {
        Reasons.Add(TEXT("baked_static_appearance_hash_invalid"));
    }
    if (!JsonStringArrayEquals(Bake, TEXT("reasons"), {})
        || IntegrationStatus != ExpectedIntegrationStatus
        || !bUmgSupportClaimed)
    {
        Reasons.Add(
            TEXT("baked_static_appearance_materialization_record_invalid"));
    }
    const TSharedPtr<FJsonObject> GateTransition = RawObjectField(
        Bake,
        TEXT("gate_transition"));
    if (!HasExactFields(
            GateTransition,
            {TEXT("before"), TEXT("after"), TEXT("satisfied")})
        || !JsonStringArrayEquals(
            GateTransition,
            TEXT("before"),
            {ExpectedGate})
        || !JsonStringArrayEquals(
            GateTransition,
            TEXT("after"),
            {})
        || !JsonStringArrayEquals(
            GateTransition,
            TEXT("satisfied"),
            {ExpectedGate}))
    {
        Reasons.Add(
            TEXT("baked_static_appearance_gate_transition_invalid"));
    }

    const TSharedPtr<FJsonObject> Source = RawObjectField(
        Bake,
        TEXT("source"));
    if (!Source)
    {
        Reasons.Add(TEXT("baked_static_appearance_source_missing"));
        return Reasons;
    }
    const bool bSourceFieldsValid = bStaticTextureBake
        ? HasExactFields(
            Source,
            {TEXT("schema"),
             TEXT("figma_node_id"),
             TEXT("logical_size"),
             TEXT("pixel_size"),
             TEXT("source_bounds"),
             TEXT("render_bounds"),
             TEXT("render_contract"),
             TEXT("effect"),
             TEXT("effect_hash"),
             TEXT("fill"),
             TEXT("shape"),
             TEXT("input_png_sha256"),
             TEXT("pixel_rgba_sha256"),
             TEXT("color_contract"),
             TEXT("intended_gate")})
        : HasExactFields(
            Source,
            {TEXT("schema"),
             TEXT("figma_node_id"),
             TEXT("logical_size"),
             TEXT("pixel_size"),
             TEXT("source_bounds"),
             TEXT("render_bounds"),
             TEXT("render_contract"),
             TEXT("effect"),
             TEXT("effect_hash"),
             TEXT("fill"),
             TEXT("shape"),
             TEXT("input_png_sha256"),
             TEXT("pixel_rgba_sha256"),
             TEXT("color_contract")});
    if (!bSourceFieldsValid)
    {
        Reasons.Add(
            TEXT("baked_static_appearance_source_contract_invalid"));
    }
    FString SourceSchema;
    FString NodeId;
    FString SourceEffectHash;
    FString InputPngHash;
    FString SourcePixelHash;
    FString SourceIntendedGate;
    Source->TryGetStringField(TEXT("schema"), SourceSchema);
    Source->TryGetStringField(TEXT("figma_node_id"), NodeId);
    Source->TryGetStringField(TEXT("effect_hash"), SourceEffectHash);
    Source->TryGetStringField(TEXT("input_png_sha256"), InputPngHash);
    Source->TryGetStringField(TEXT("pixel_rgba_sha256"), SourcePixelHash);
    Source->TryGetStringField(
        TEXT("intended_gate"),
        SourceIntendedGate);
    if (SourceSchema != ExpectedSchema)
    {
        Reasons.Add(TEXT("baked_static_appearance_schema_unsupported"));
    }
    if ((bStaticTextureBake && SourceIntendedGate != ExpectedGate)
        || (!bStaticTextureBake && Source->HasField(TEXT("intended_gate"))))
    {
        Reasons.Add(
            TEXT("baked_static_appearance_intended_gate_invalid"));
    }
    if (NodeId.IsEmpty())
    {
        Reasons.Add(TEXT("baked_static_appearance_node_id_invalid"));
    }
    if (!IsSha256Hex(InputPngHash)
        || !SourcePixelHash.Equals(PixelHash, ESearchCase::IgnoreCase))
    {
        Reasons.Add(TEXT("baked_static_appearance_pixel_hash_mismatch"));
    }
    if (!CanonicalJsonObjectMatches(
            SourceCanonicalJson,
            Source,
            SourceHash))
    {
        Reasons.Add(TEXT("baked_static_appearance_source_hash_mismatch"));
    }

    const TSharedPtr<FJsonObject> Effect = RawObjectField(
        Source,
        TEXT("effect"));
    if (!(bStaticTextureBake
            ? ValidateStaticTextureEffect(Effect)
            : ValidateStaticAppearanceEffect(Effect)))
    {
        Reasons.Add(TEXT("baked_static_appearance_effect_invalid"));
    }
    if (!EffectHash.Equals(SourceEffectHash, ESearchCase::IgnoreCase)
        || !CanonicalJsonObjectMatches(
            EffectCanonicalJson,
            Effect,
            EffectHash))
    {
        Reasons.Add(
            TEXT("baked_static_appearance_effect_hash_mismatch"));
    }

    const TSharedPtr<FJsonObject> LogicalSize = RawObjectField(
        Source,
        TEXT("logical_size"));
    double LogicalWidth = 0.0;
    double LogicalHeight = 0.0;
    const bool bLogicalSizeValid = HasExactFields(
            LogicalSize,
            {TEXT("width"), TEXT("height")})
        && TryGetFiniteNumber(LogicalSize, TEXT("width"), LogicalWidth)
        && TryGetFiniteNumber(LogicalSize, TEXT("height"), LogicalHeight)
        && LogicalWidth > 0.0
        && LogicalHeight > 0.0
        && FMath::IsNearlyEqual(
            LogicalWidth,
            FMath::RoundToDouble(LogicalWidth),
            StaticAppearanceBakeBoundsEpsilon)
        && FMath::IsNearlyEqual(
            LogicalHeight,
            FMath::RoundToDouble(LogicalHeight),
            StaticAppearanceBakeBoundsEpsilon)
        && LogicalWidth <= StaticAppearanceBakeMaxDimension
        && LogicalHeight <= StaticAppearanceBakeMaxDimension
        && LogicalWidth * LogicalHeight <= StaticAppearanceBakeMaxPixels;
    if (!bLogicalSizeValid)
    {
        Reasons.Add(TEXT("baked_static_appearance_logical_size_invalid"));
    }
    const int32 PixelWidth = bLogicalSizeValid
        ? FMath::RoundToInt(LogicalWidth)
        : 0;
    const int32 PixelHeight = bLogicalSizeValid
        ? FMath::RoundToInt(LogicalHeight)
        : 0;
    const TSharedPtr<FJsonObject> PixelSize = RawObjectField(
        Source,
        TEXT("pixel_size"));
    double DeclaredPixelWidth = 0.0;
    double DeclaredPixelHeight = 0.0;
    if (!HasExactFields(PixelSize, {TEXT("width"), TEXT("height")})
        || !HasRawIntegerField(PixelSize, TEXT("width"))
        || !HasRawIntegerField(PixelSize, TEXT("height"))
        || !PixelSize->TryGetNumberField(TEXT("width"), DeclaredPixelWidth)
        || !PixelSize->TryGetNumberField(TEXT("height"), DeclaredPixelHeight)
        || DeclaredPixelWidth != PixelWidth
        || DeclaredPixelHeight != PixelHeight)
    {
        Reasons.Add(TEXT("baked_static_appearance_pixel_size_invalid"));
    }
    if (!bLogicalSizeValid
        || !Layer.Size.Equals(
            FVector2D(LogicalWidth, LogicalHeight),
            StaticAppearanceBakeBoundsEpsilon))
    {
        Reasons.Add(TEXT("baked_static_appearance_layer_size_mismatch"));
    }

    const TSharedPtr<FJsonObject> SourceBounds = RawObjectField(
        Source,
        TEXT("source_bounds"));
    const TSharedPtr<FJsonObject> RenderBounds = RawObjectField(
        Source,
        TEXT("render_bounds"));
    double SourceX = 0.0;
    double SourceY = 0.0;
    double SourceWidth = 0.0;
    double SourceHeight = 0.0;
    double RenderX = 0.0;
    double RenderY = 0.0;
    double RenderWidth = 0.0;
    double RenderHeight = 0.0;
    const bool bBoundsValid = HasExactFields(
            SourceBounds,
            {TEXT("x"), TEXT("y"), TEXT("width"), TEXT("height")})
        && HasExactFields(
            RenderBounds,
            {TEXT("x"), TEXT("y"), TEXT("width"), TEXT("height")})
        && TryGetFiniteNumber(SourceBounds, TEXT("x"), SourceX)
        && TryGetFiniteNumber(SourceBounds, TEXT("y"), SourceY)
        && TryGetFiniteNumber(SourceBounds, TEXT("width"), SourceWidth)
        && TryGetFiniteNumber(SourceBounds, TEXT("height"), SourceHeight)
        && TryGetFiniteNumber(RenderBounds, TEXT("x"), RenderX)
        && TryGetFiniteNumber(RenderBounds, TEXT("y"), RenderY)
        && TryGetFiniteNumber(RenderBounds, TEXT("width"), RenderWidth)
        && TryGetFiniteNumber(RenderBounds, TEXT("height"), RenderHeight)
        && SourceWidth > 0.0
        && SourceHeight > 0.0;
    if (!bBoundsValid
        || !FMath::IsNearlyEqual(
            SourceX,
            RenderX,
            StaticAppearanceBakeBoundsEpsilon)
        || !FMath::IsNearlyEqual(
            SourceY,
            RenderY,
            StaticAppearanceBakeBoundsEpsilon)
        || !FMath::IsNearlyEqual(
            SourceWidth,
            RenderWidth,
            StaticAppearanceBakeBoundsEpsilon)
        || !FMath::IsNearlyEqual(
            SourceHeight,
            RenderHeight,
            StaticAppearanceBakeBoundsEpsilon)
        || !FMath::IsNearlyEqual(
            SourceWidth,
            LogicalWidth,
            StaticAppearanceBakeBoundsEpsilon)
        || !FMath::IsNearlyEqual(
            SourceHeight,
            LogicalHeight,
            StaticAppearanceBakeBoundsEpsilon))
    {
        Reasons.Add(TEXT("baked_static_appearance_bounds_mismatch"));
    }

    const TSharedPtr<FJsonObject> Provenance = RawObjectField(
        Bake,
        TEXT("provenance"));
    const TSharedPtr<FJsonObject> ProvenanceSourceBounds = RawObjectField(
        Provenance,
        TEXT("source_bounds"));
    const TSharedPtr<FJsonObject> ProvenanceRenderBounds = RawObjectField(
        Provenance,
        TEXT("render_bounds"));
    FString ProvenanceSource;
    FString ProvenanceNodeId;
    FString ProvenanceFormat;
    FString ProvenanceInputHash;
    FString ProvenancePixelHash;
    double ProvenanceScale = 0.0;
    if (!HasExactFields(
            Provenance,
            {TEXT("source"),
             TEXT("figma_node_id"),
             TEXT("format"),
             TEXT("scale"),
             TEXT("source_bounds"),
             TEXT("render_bounds"),
             TEXT("input_png_sha256"),
             TEXT("input_pixel_rgba_sha256")})
        || !Provenance->TryGetStringField(
            TEXT("source"),
            ProvenanceSource)
        || ProvenanceSource != TEXT("figma_render_api")
        || !Provenance->TryGetStringField(
            TEXT("figma_node_id"),
            ProvenanceNodeId)
        || ProvenanceNodeId != NodeId
        || !Provenance->TryGetStringField(
            TEXT("format"),
            ProvenanceFormat)
        || ProvenanceFormat != TEXT("png")
        || !TryGetFiniteNumber(Provenance, TEXT("scale"), ProvenanceScale)
        || !FMath::IsNearlyEqual(ProvenanceScale, 1.0, 0.000001)
        || !Provenance->TryGetStringField(
            TEXT("input_png_sha256"),
            ProvenanceInputHash)
        || !ProvenanceInputHash.Equals(InputPngHash, ESearchCase::IgnoreCase)
        || !Provenance->TryGetStringField(
            TEXT("input_pixel_rgba_sha256"),
            ProvenancePixelHash)
        || !ProvenancePixelHash.Equals(PixelHash, ESearchCase::IgnoreCase)
        || !SourceBounds
        || !RenderBounds
        || !ProvenanceSourceBounds
        || !ProvenanceRenderBounds
        || !FJsonValue::CompareEqual(
            FJsonValueObject(SourceBounds),
            FJsonValueObject(ProvenanceSourceBounds))
        || !FJsonValue::CompareEqual(
            FJsonValueObject(RenderBounds),
            FJsonValueObject(ProvenanceRenderBounds)))
    {
        Reasons.Add(TEXT("baked_static_appearance_provenance_invalid"));
    }

    const TSharedPtr<FJsonObject> RenderContract = RawObjectField(
        Source,
        TEXT("render_contract"));
    FString RenderSource;
    FString RenderFormat;
    double RenderScale = 0.0;
    if (!HasExactFields(
            RenderContract,
            {TEXT("source"), TEXT("format"), TEXT("scale")})
        || !RenderContract->TryGetStringField(
            TEXT("source"),
            RenderSource)
        || RenderSource != TEXT("figma_render_api")
        || !RenderContract->TryGetStringField(
            TEXT("format"),
            RenderFormat)
        || RenderFormat != TEXT("png")
        || !TryGetFiniteNumber(RenderContract, TEXT("scale"), RenderScale)
        || !FMath::IsNearlyEqual(RenderScale, 1.0, 0.000001))
    {
        Reasons.Add(
            TEXT("baked_static_appearance_render_contract_invalid"));
    }

    const TSharedPtr<FJsonObject> Fill = RawObjectField(
        Source,
        TEXT("fill"));
    FString FillType;
    FString FillColor;
    FString FillBlendMode;
    double FillOpacity = 0.0;
    if (!HasExactFields(
            Fill,
            {TEXT("type"), TEXT("color"), TEXT("opacity"), TEXT("blend_mode")})
        || !Fill->TryGetStringField(TEXT("type"), FillType)
        || FillType != TEXT("solid")
        || !Fill->TryGetStringField(TEXT("color"), FillColor)
        || !IsUppercaseMaterialColor(FillColor)
        || !Fill->TryGetStringField(TEXT("blend_mode"), FillBlendMode)
        || FillBlendMode != TEXT("normal")
        || !TryGetFiniteNumber(Fill, TEXT("opacity"), FillOpacity)
        || FillOpacity < 0.0
        || FillOpacity > 1.0)
    {
        Reasons.Add(TEXT("baked_static_appearance_fill_invalid"));
    }

    const TSharedPtr<FJsonObject> Shape = RawObjectField(
        Source,
        TEXT("shape"));
    const TSharedPtr<FJsonObject> CornerRadii = RawObjectField(
        Shape,
        TEXT("corner_radii"));
    FString ShapeKind;
    double Smoothing = 0.0;
    bool bShapeValid = HasExactFields(
            Shape,
            {TEXT("kind"), TEXT("corner_radii"), TEXT("corner_smoothing")})
        && Shape->TryGetStringField(TEXT("kind"), ShapeKind)
        && ShapeKind == TEXT("rectangle")
        && HasExactFields(
            CornerRadii,
            {TEXT("top_left"),
             TEXT("top_right"),
             TEXT("bottom_right"),
             TEXT("bottom_left")})
        && TryGetFiniteNumber(
            Shape,
            TEXT("corner_smoothing"),
            Smoothing)
        && Smoothing >= 0.0
        && Smoothing <= 1.0;
    for (const TCHAR* Field : {
             TEXT("top_left"),
             TEXT("top_right"),
             TEXT("bottom_right"),
             TEXT("bottom_left")})
    {
        double Radius = 0.0;
        bShapeValid = bShapeValid
            && TryGetFiniteNumber(CornerRadii, Field, Radius)
            && Radius >= 0.0;
    }
    if (!bShapeValid)
    {
        Reasons.Add(TEXT("baked_static_appearance_shape_invalid"));
    }

    const TSharedPtr<FJsonObject> ColorContract = RawObjectField(
        Source,
        TEXT("color_contract"));
    FString ColorSpace;
    FString AlphaMode;
    double ChannelDepth = 0.0;
    double RenderingIntent = -1.0;
    if (!HasExactFields(
            ColorContract,
            {TEXT("color_space"),
             TEXT("alpha_mode"),
             TEXT("channel_depth_bits"),
             TEXT("png_srgb_rendering_intent")})
        || !ColorContract->TryGetStringField(
            TEXT("color_space"),
            ColorSpace)
        || ColorSpace != TEXT("sRGB")
        || !ColorContract->TryGetStringField(
            TEXT("alpha_mode"),
            AlphaMode)
        || AlphaMode != TEXT("straight")
        || !HasRawIntegerField(
            ColorContract,
            TEXT("channel_depth_bits"))
        || !ColorContract->TryGetNumberField(
            TEXT("channel_depth_bits"),
            ChannelDepth)
        || ChannelDepth != 8.0
        || !HasRawIntegerField(
            ColorContract,
            TEXT("png_srgb_rendering_intent"))
        || !ColorContract->TryGetNumberField(
            TEXT("png_srgb_rendering_intent"),
            RenderingIntent)
        || RenderingIntent != 0.0)
    {
        Reasons.Add(
            TEXT("baked_static_appearance_color_contract_invalid"));
    }

    const TSharedPtr<FJsonObject> Layout = RawObjectField(
        Bake,
        TEXT("layout_preservation"));
    FString LayoutPolicy;
    double PreservedRotation = 0.0;
    if (!HasExactFields(
            Layout,
            {TEXT("policy"),
             TEXT("Size"),
             TEXT("Anchor"),
             TEXT("RenderTransformPivot"),
             TEXT("Position"),
             TEXT("RotationDegrees"),
             TEXT("CanvasSlot")})
        || !Layout->TryGetStringField(TEXT("policy"), LayoutPolicy)
        || LayoutPolicy != TEXT("preserve_exact_layer_layout")
        || !JsonVectorEquals(
            RawObjectField(Layout, TEXT("Size")),
            Layer.Size)
        || !JsonVectorEquals(
            RawObjectField(Layout, TEXT("Anchor")),
            Layer.Anchor)
        || !JsonVectorEquals(
            RawObjectField(Layout, TEXT("RenderTransformPivot")),
            Layer.RenderTransformPivot)
        || !JsonVectorEquals(
            RawObjectField(Layout, TEXT("Position")),
            Layer.Position)
        || !TryGetFiniteNumber(
            Layout,
            TEXT("RotationDegrees"),
            PreservedRotation)
        || !FMath::IsNearlyEqual(
            PreservedRotation,
            Layer.RotationDegrees,
            0.000001)
        || !FMath::IsNearlyZero(Layer.RotationDegrees, 0.000001)
        || !JsonCanvasSlotEquals(
            RawObjectField(Layout, TEXT("CanvasSlot")),
            Layer.CanvasSlot)
        || Bake->HasField(TEXT("layout_adjustment"))
        || Source->HasField(TEXT("padding")))
    {
        Reasons.Add(
            TEXT("baked_static_appearance_layout_preservation_invalid"));
    }

    const FString* BakedSourcePath = ResourceSourcePaths.Find(Layer.AssetId);
    if (!BakedSourcePath
        || !bLogicalSizeValid
        || !ValidateStaticAppearancePng(
            *BakedSourcePath,
            PixelWidth,
            PixelHeight,
            PixelHash))
    {
        Reasons.Add(
            TEXT("baked_static_appearance_png_contract_invalid"));
    }
    return Reasons;
}

TArray<FString> ValidateMaterializedBakedLayer(
    const FTigerStudioUMGLayerRecord& Layer,
    const int32 SchemaVersion,
    const TMap<FString, FString>& ResourceKinds,
    const TMap<FString, FString>& ParentPanelKinds,
    const TMap<FString, FTigerStudioUMGResourceRecord>& ResourcesById,
    const TMap<FString, FString>& ResourceFileHashes,
    const TMap<FString, FString>& ResourceSourcePaths)
{
    TArray<FString> Reasons;
    if (SchemaVersion < 13)
    {
        Reasons.Add(TEXT("baked_generation_unavailable"));
        return Reasons;
    }
    if (Layer.Kind != ETigerStudioUMGLayerKind::Image)
    {
        Reasons.Add(TEXT("baked_static_vector_layer_kind_unsupported"));
    }
    if (!Layer.BlockReasons.IsEmpty())
    {
        Reasons.Add(TEXT("baked_block_reasons_must_be_empty"));
    }
    if (!IsEmptyMaterialRecord(Layer.Material)
        || !IsEmptyFlipbookRecord(Layer.Flipbook))
    {
        Reasons.Add(TEXT("baked_conflicting_visual_record"));
    }
    for (const FString& ImageReason : ValidateImageFillLayer(
             Layer,
             SchemaVersion,
             ResourceKinds,
             ParentPanelKinds))
    {
        Reasons.AddUnique(ImageReason);
    }

    const FTigerStudioUMGImageFillRecord& ImageFill = Layer.ImageFill;
    if (Layer.AssetId.IsEmpty()
        || ImageFill.AssetId.IsEmpty()
        || Layer.AssetId != ImageFill.AssetId)
    {
        Reasons.Add(TEXT("baked_asset_id_mismatch"));
    }
    if (ImageFill.Mode != TEXT("Stretch")
        || !ImageFill.SourceSize.Equals(Layer.Size, 0.000001)
        || !ImageFill.FocalPoint.Equals(FVector2D(0.5, 0.5), 0.000001)
        || !FMath::IsNearlyEqual(ImageFill.TileScale, 1.0, 0.000001)
        || ImageFill.Crop.Enabled
        || ImageFill.Crop.Units != TEXT("Normalized")
        || !FMath::IsNearlyZero(ImageFill.Crop.X, 0.000001)
        || !FMath::IsNearlyZero(ImageFill.Crop.Y, 0.000001)
        || !FMath::IsNearlyEqual(ImageFill.Crop.Width, 1.0, 0.000001)
        || !FMath::IsNearlyEqual(ImageFill.Crop.Height, 1.0, 0.000001)
        || ImageFill.NineSlice.Enabled
        || ImageFill.NineSlice.Units != TEXT("Pixels")
        || !FMath::IsNearlyZero(ImageFill.NineSlice.Left, 0.000001)
        || !FMath::IsNearlyZero(ImageFill.NineSlice.Top, 0.000001)
        || !FMath::IsNearlyZero(ImageFill.NineSlice.Right, 0.000001)
        || !FMath::IsNearlyZero(ImageFill.NineSlice.Bottom, 0.000001)
        || !FMath::IsNearlyZero(ImageFill.CornerRadii.X, 0.000001)
        || !FMath::IsNearlyZero(ImageFill.CornerRadii.Y, 0.000001)
        || !FMath::IsNearlyZero(ImageFill.CornerRadii.Z, 0.000001)
        || !FMath::IsNearlyZero(ImageFill.CornerRadii.W, 0.000001)
        || !FMath::IsNearlyEqual(ImageFill.Opacity, 1.0, 0.000001)
        || !ImageFill.Tint.Equals(TEXT("#FFFFFFFF"), ESearchCase::IgnoreCase)
        || HasUnsupportedImageAdjustments(ImageFill.Adjustments))
    {
        Reasons.Add(TEXT("baked_image_fill_contract_invalid"));
    }

    TSharedPtr<FJsonObject> Payload;
    const TSharedRef<TJsonReader<>> PayloadReader =
        TJsonReaderFactory<>::Create(Layer.PayloadJson);
    if (!FJsonSerializer::Deserialize(PayloadReader, Payload) || !Payload)
    {
        Reasons.Add(TEXT("baked_payload_json_invalid"));
        return Reasons;
    }
    const TSharedPtr<FJsonObject>* StaticVectorBakeField = nullptr;
    const TSharedPtr<FJsonObject>* StaticAppearanceBakeField = nullptr;
    const bool bHasStaticVectorBakeRecord = Payload->TryGetObjectField(
            TEXT("static_vector_bake"),
            StaticVectorBakeField)
        && StaticVectorBakeField
        && StaticVectorBakeField->IsValid();
    const bool bHasStaticAppearanceBakeRecord = Payload->TryGetObjectField(
            TEXT("static_appearance_bake"),
            StaticAppearanceBakeField)
        && StaticAppearanceBakeField
        && StaticAppearanceBakeField->IsValid();
    FString StaticVectorStatus;
    FString StaticAppearanceStatus;
    if (bHasStaticVectorBakeRecord)
    {
        (*StaticVectorBakeField)->TryGetStringField(
            TEXT("status"),
            StaticVectorStatus);
    }
    if (bHasStaticAppearanceBakeRecord)
    {
        (*StaticAppearanceBakeField)->TryGetStringField(
            TEXT("status"),
            StaticAppearanceStatus);
    }
    const bool bHasStaticVectorBake = bHasStaticVectorBakeRecord
        && (StaticVectorStatus == TEXT("available")
            || StaticVectorStatus == TEXT("materialized"));
    const bool bHasStaticAppearanceBake = bHasStaticAppearanceBakeRecord
        && (StaticAppearanceStatus == TEXT("available")
            || StaticAppearanceStatus == TEXT("materialized"));
    if (bHasStaticVectorBake == bHasStaticAppearanceBake)
    {
        Reasons.Add(
            bHasStaticVectorBake
                ? TEXT("baked_plan_kind_conflict")
                : TEXT("baked_static_vector_record_missing"));
        return Reasons;
    }
    const TSharedPtr<FJsonObject> Bake = bHasStaticAppearanceBake
        ? *StaticAppearanceBakeField
        : *StaticVectorBakeField;
    bool bStaticTextureBake = false;
    const TCHAR* ExpectedBakeGate = StaticVectorBakeGate;
    if (bHasStaticAppearanceBake)
    {
        const TSharedPtr<FJsonObject> AppearanceSource = RawObjectField(
            Bake,
            TEXT("source"));
        const TSharedPtr<FJsonObject> AppearanceEffect = RawObjectField(
            AppearanceSource,
            TEXT("effect"));
        FString AppearanceKind;
        FString AppearanceEffectType;
        FString Mapping;
        FString Conversion;
        Bake->TryGetStringField(TEXT("kind"), AppearanceKind);
        if (AppearanceEffect)
        {
            AppearanceEffect->TryGetStringField(
                TEXT("type"),
                AppearanceEffectType);
        }
        Payload->TryGetStringField(TEXT("umg_mapping"), Mapping);
        Payload->TryGetStringField(
            TEXT("painter_conversion"),
            Conversion);
        const bool bNoiseContract =
            AppearanceKind == StaticAppearanceBakeKind
            && AppearanceEffectType == TEXT("noise")
            && Mapping
                == TEXT(
                    "texture2d_image_fill_from_static_appearance_bake")
            && Conversion == TEXT("static_appearance_png_bake");
        const bool bTextureContract =
            AppearanceKind == StaticTextureBakeKind
            && AppearanceEffectType == TEXT("texture")
            && Mapping
                == TEXT(
                    "texture2d_image_fill_from_static_texture_bake")
            && Conversion == TEXT("static_texture_png_bake");
        if (bNoiseContract == bTextureContract)
        {
            Reasons.Add(
                TEXT("baked_static_appearance_contract_mismatch"));
            return Reasons;
        }
        bStaticTextureBake = bTextureContract;
        ExpectedBakeGate = bStaticTextureBake
            ? StaticTextureBakeGate
            : StaticAppearanceBakeGate;
        const int32 RequiredAppearanceSchema = bStaticTextureBake
            ? StaticTextureBakeSchemaVersion
            : StaticAppearanceBakeSchemaVersion;
        if (SchemaVersion < RequiredAppearanceSchema)
        {
            Reasons.Add(
                bStaticTextureBake
                    ? TEXT("baked_static_texture_requires_schema_15")
                    : TEXT("static_appearance_bake_requires_schema_14"));
            return Reasons;
        }
    }
    FString Status;
    FString SourceHash;
    FString ContentHash;
    FString PixelHash;
    FString OriginDisposition;
    FString SatisfiedGate;
    FString ManifestPath;
    FString PngPath;
    bool bAvailable = false;
    Bake->TryGetStringField(TEXT("status"), Status);
    Bake->TryGetStringField(TEXT("source_hash"), SourceHash);
    Bake->TryGetStringField(TEXT("content_hash"), ContentHash);
    Bake->TryGetStringField(TEXT("pixel_rgba_sha256"), PixelHash);
    Bake->TryGetStringField(
        TEXT("origin_disposition"),
        OriginDisposition);
    Bake->TryGetStringField(TEXT("satisfied_gate"), SatisfiedGate);
    Bake->TryGetStringField(TEXT("manifest_path"), ManifestPath);
    Bake->TryGetStringField(TEXT("png_path"), PngPath);
    Bake->TryGetBoolField(TEXT("available"), bAvailable);
    if (Status != TEXT("materialized") || !bAvailable)
    {
        Reasons.Add(TEXT("baked_materialization_record_invalid"));
    }
    if (!IsSha256Hex(SourceHash)
        || !IsSha256Hex(ContentHash)
        || !IsSha256Hex(PixelHash))
    {
        Reasons.Add(TEXT("baked_hash_invalid"));
    }
    if (OriginDisposition != TEXT("Baked"))
    {
        Reasons.Add(TEXT("baked_origin_disposition_invalid"));
    }
    if (SatisfiedGate != ExpectedBakeGate)
    {
        Reasons.Add(TEXT("baked_satisfied_gate_invalid"));
    }
    if (!IsSafeRelativeArtifactPath(ManifestPath, TEXT("json"))
        || !IsSafeRelativeArtifactPath(PngPath, TEXT("png")))
    {
        Reasons.Add(TEXT("baked_artifact_path_invalid"));
    }
    if (!ContentHash.IsEmpty()
        && Layer.AssetId != TEXT("texture_") + ContentHash)
    {
        Reasons.Add(TEXT("baked_asset_id_mismatch"));
    }
    const FTigerStudioUMGResourceRecord* Resource =
        ResourcesById.Find(Layer.AssetId);
    if (!Resource)
    {
        Reasons.Add(TEXT("baked_resource_missing"));
    }
    else
    {
        const FString ExpectedDestination = TEXT("TS_texture_") + ContentHash;
        if (!Resource->Kind.Equals(TEXT("texture"), ESearchCase::IgnoreCase))
        {
            Reasons.Add(TEXT("baked_resource_kind_unsupported"));
        }
        if (!Resource->ContentHash.Equals(ContentHash, ESearchCase::IgnoreCase))
        {
            Reasons.Add(TEXT("baked_resource_content_hash_mismatch"));
        }
        if (Resource->DestinationName != ExpectedDestination)
        {
            Reasons.Add(TEXT("baked_resource_destination_name_invalid"));
        }
        const FString* ActualHash = ResourceFileHashes.Find(Resource->Id);
        if (!ActualHash
            || !ActualHash->Equals(ContentHash, ESearchCase::IgnoreCase))
        {
            Reasons.Add(TEXT("baked_resource_file_hash_mismatch"));
        }
        TSharedPtr<FJsonObject> Settings;
        const TSharedRef<TJsonReader<>> SettingsReader =
            TJsonReaderFactory<>::Create(Resource->SettingsJson);
        FString Usage;
        bool bSRGB = false;
        if (!FJsonSerializer::Deserialize(SettingsReader, Settings)
            || !Settings
            || Settings->Values.Num() != 2
            || !Settings->TryGetStringField(TEXT("Usage"), Usage)
            || Usage != TEXT("ImageFill")
            || !Settings->TryGetBoolField(TEXT("SRGB"), bSRGB)
            || !bSRGB)
        {
            Reasons.Add(TEXT("baked_resource_settings_invalid"));
        }
    }

    if (bHasStaticAppearanceBake)
    {
        Reasons.Append(ValidateMaterializedStaticAppearanceBake(
            Layer,
            Bake,
            SourceHash,
            PixelHash,
            ResourceSourcePaths,
            bStaticTextureBake));
        return Reasons;
    }

    const TSharedPtr<FJsonObject> Source = RawObjectField(
        Bake,
        TEXT("source"));
    FString SourceSchema;
    if (!Source
        || !Source->TryGetStringField(TEXT("schema"), SourceSchema)
        || SourceSchema != StaticVectorBakeSchema)
    {
        Reasons.Add(TEXT("baked_static_vector_schema_unsupported"));
    }
    FString CanonicalSource;
    FString ComputedSourceHash;
    if (!Source
        || Source->Values.Num() != 9
        || !AppendCanonicalJson(
            MakeShared<FJsonValueObject>(Source),
            TEXT("source"),
            CanonicalSource)
        || !HashUtf8Sha256(CanonicalSource, ComputedSourceHash)
        || !ComputedSourceHash.Equals(SourceHash, ESearchCase::IgnoreCase))
    {
        Reasons.Add(TEXT("baked_static_vector_source_hash_mismatch"));
    }
    const TArray<TSharedPtr<FJsonValue>>* FillRgba = nullptr;
    bool bFillValid = Source
        && Source->TryGetArrayField(TEXT("fill_rgba"), FillRgba)
        && FillRgba
        && FillRgba->Num() == 4;
    if (bFillValid)
    {
        for (int32 Index = 0; Index < FillRgba->Num(); ++Index)
        {
            const TSharedPtr<FJsonValue>& Channel = (*FillRgba)[Index];
            const double Value = Channel && Channel->Type == EJson::Number
                ? Channel->AsNumber()
                : -1.0;
            if (!FMath::IsNearlyEqual(
                    Value,
                    FMath::RoundToDouble(Value),
                    0.000001)
                || Value < 0.0
                || Value > 255.0
                || (Index == 3 && Value <= 0.0))
            {
                bFillValid = false;
                break;
            }
        }
    }
    if (!bFillValid)
    {
        Reasons.Add(TEXT("baked_static_vector_fill_invalid"));
    }
    const TSharedPtr<FJsonObject> Renderer = RawObjectField(
        Source,
        TEXT("renderer"));
    FString RendererId;
    FString QtVersion;
    bool bAntialiasing = false;
    if (!Renderer
        || !Renderer->TryGetStringField(TEXT("id"), RendererId)
        || RendererId != StaticVectorBakeRenderer
        || !Renderer->TryGetStringField(TEXT("qt_version"), QtVersion)
        || QtVersion.IsEmpty()
        || !Renderer->TryGetBoolField(
            TEXT("antialiasing"),
            bAntialiasing)
        || !bAntialiasing)
    {
        Reasons.Add(TEXT("baked_static_vector_renderer_invalid"));
    }

    const TSharedPtr<FJsonObject> ColorContract = RawObjectField(
        Source,
        TEXT("color_contract"));
    FString ColorSpace;
    FString AlphaMode;
    double ChannelDepthBits = 0.0;
    double RenderingIntent = -1.0;
    if (!ColorContract
        || !ColorContract->TryGetStringField(
            TEXT("color_space"),
            ColorSpace)
        || ColorSpace != TEXT("sRGB")
        || !ColorContract->TryGetStringField(
            TEXT("alpha_mode"),
            AlphaMode)
        || AlphaMode != TEXT("straight")
        || !HasRawIntegerField(
            ColorContract,
            TEXT("channel_depth_bits"))
        || !ColorContract->TryGetNumberField(
            TEXT("channel_depth_bits"),
            ChannelDepthBits)
        || !FMath::IsNearlyEqual(ChannelDepthBits, 8.0, 0.000001)
        || !HasRawIntegerField(
            ColorContract,
            TEXT("png_srgb_rendering_intent"))
        || !ColorContract->TryGetNumberField(
            TEXT("png_srgb_rendering_intent"),
            RenderingIntent)
        || !FMath::IsNearlyZero(RenderingIntent, 0.000001))
    {
        Reasons.Add(TEXT("baked_static_vector_color_contract_invalid"));
    }

    const TArray<TSharedPtr<FJsonValue>>* Geometry = nullptr;
    TArray<FIntPoint> ActualSubpathIndices;
    int32 ActualPathBytes = 0;
    int32 ActualTokenCount = 0;
    bool bGeometryValid = Source
        && Source->TryGetArrayField(TEXT("geometry"), Geometry)
        && Geometry
        && !Geometry->IsEmpty()
        && Geometry->Num() <= StaticVectorBakeMaxSubpaths;
    if (bGeometryValid)
    {
        for (int32 RowIndex = 0; RowIndex < Geometry->Num(); ++RowIndex)
        {
            const TSharedPtr<FJsonObject> Row = (*Geometry)[RowIndex]
                && (*Geometry)[RowIndex]->Type == EJson::Object
                ? (*Geometry)[RowIndex]->AsObject()
                : nullptr;
            FString Path;
            FString WindingRule;
            int32 RowSubpaths = 0;
            int32 RowTokens = 0;
            bGeometryValid = Row
                && Row->Values.Num() == 2
                && Row->TryGetStringField(TEXT("path"), Path)
                && Row->TryGetStringField(TEXT("winding_rule"), WindingRule)
                && (WindingRule == TEXT("evenodd")
                    || WindingRule == TEXT("nonzero"))
                && ValidateStaticVectorPathSyntax(
                    Path,
                    RowSubpaths,
                    RowTokens);
            if (!bGeometryValid)
            {
                break;
            }
            FTCHARToUTF8 PathUtf8(*Path);
            ActualPathBytes += PathUtf8.Length();
            ActualTokenCount += RowTokens;
            for (int32 LocalIndex = 0; LocalIndex < RowSubpaths; ++LocalIndex)
            {
                ActualSubpathIndices.Add(FIntPoint(RowIndex, LocalIndex));
            }
            if (ActualSubpathIndices.Num() > StaticVectorBakeMaxSubpaths)
            {
                bGeometryValid = false;
                break;
            }
        }
    }
    const TSharedPtr<FJsonObject> GeometryComplexity = RawObjectField(
        Source,
        TEXT("geometry_complexity"));
    double DeclaredRows = 0.0;
    double DeclaredBytes = 0.0;
    double DeclaredTokens = 0.0;
    bGeometryValid = bGeometryValid
        && GeometryComplexity
        && GeometryComplexity->Values.Num() == 3
        && HasRawIntegerField(GeometryComplexity, TEXT("row_count"))
        && GeometryComplexity->TryGetNumberField(
            TEXT("row_count"), DeclaredRows)
        && DeclaredRows == Geometry->Num()
        && HasRawIntegerField(GeometryComplexity, TEXT("path_bytes"))
        && GeometryComplexity->TryGetNumberField(
            TEXT("path_bytes"), DeclaredBytes)
        && DeclaredBytes == ActualPathBytes
        && HasRawIntegerField(GeometryComplexity, TEXT("token_count"))
        && GeometryComplexity->TryGetNumberField(
            TEXT("token_count"), DeclaredTokens)
        && DeclaredTokens == ActualTokenCount;
    if (!bGeometryValid)
    {
        Reasons.Add(TEXT("baked_static_vector_geometry_invalid"));
    }

    const TSharedPtr<FJsonObject> LogicalSize = RawObjectField(
        Source,
        TEXT("logical_size"));
    double LogicalWidth = 0.0;
    double LogicalHeight = 0.0;
    const bool bLogicalSizeValid = LogicalSize
        && LogicalSize->TryGetNumberField(TEXT("width"), LogicalWidth)
        && LogicalSize->TryGetNumberField(TEXT("height"), LogicalHeight)
        && FMath::IsFinite(LogicalWidth)
        && FMath::IsFinite(LogicalHeight)
        && LogicalWidth > 0.0
        && LogicalHeight > 0.0;
    double SourcePadding = 0.0;
    if (!Source
        || !HasRawIntegerField(Source, TEXT("padding"))
        || !Source->TryGetNumberField(TEXT("padding"), SourcePadding)
        || !FMath::IsNearlyEqual(SourcePadding, 2.0, 0.000001))
    {
        Reasons.Add(TEXT("baked_static_vector_padding_invalid"));
    }
    const double ExpandedWidth = LogicalWidth + SourcePadding * 2.0;
    const double ExpandedHeight = LogicalHeight + SourcePadding * 2.0;
    if (!bLogicalSizeValid
        || !Layer.Size.Equals(
            FVector2D(ExpandedWidth, ExpandedHeight),
            0.000001))
    {
        Reasons.Add(TEXT("baked_layer_size_mismatch"));
    }
    const FString* BakedSourcePath = ResourceSourcePaths.Find(Layer.AssetId);
    if (!BakedSourcePath
        || !ValidateStaticVectorPng(
            *BakedSourcePath,
            FMath::RoundToInt(ExpandedWidth),
            FMath::RoundToInt(ExpandedHeight)))
    {
        Reasons.Add(TEXT("baked_resource_png_contract_invalid"));
    }
    const TSharedPtr<FJsonObject> LayoutAdjustment = RawObjectField(
        Bake,
        TEXT("layout_adjustment"));
    const auto JsonVectorEquals = [](
        const TSharedPtr<FJsonObject>& Object,
        const double X,
        const double Y)
    {
        double ActualX = 0.0;
        double ActualY = 0.0;
        return Object
            && Object->Values.Num() == 2
            && Object->TryGetNumberField(TEXT("X"), ActualX)
            && Object->TryGetNumberField(TEXT("Y"), ActualY)
            && FMath::IsNearlyEqual(ActualX, X, 0.000001)
            && FMath::IsNearlyEqual(ActualY, Y, 0.000001);
    };
    const TSharedPtr<FJsonObject> OriginalSize = RawObjectField(
        LayoutAdjustment,
        TEXT("original_size"));
    const TSharedPtr<FJsonObject> ExpandedSize = RawObjectField(
        LayoutAdjustment,
        TEXT("expanded_size"));
    const TSharedPtr<FJsonObject> OriginalPivot = RawObjectField(
        LayoutAdjustment,
        TEXT("original_pivot"));
    const TSharedPtr<FJsonObject> ExpandedPivot = RawObjectField(
        LayoutAdjustment,
        TEXT("expanded_pivot"));
    const TSharedPtr<FJsonObject> PositionPreserved = RawObjectField(
        LayoutAdjustment,
        TEXT("position_preserved"));
    double OriginalPivotX = 0.0;
    double OriginalPivotY = 0.0;
    double RotationPreserved = 0.0;
    const bool bOriginalPivotValid = OriginalPivot
        && OriginalPivot->TryGetNumberField(TEXT("X"), OriginalPivotX)
        && OriginalPivot->TryGetNumberField(TEXT("Y"), OriginalPivotY)
        && FMath::IsWithinInclusive(OriginalPivotX, 0.0, 1.0)
        && FMath::IsWithinInclusive(OriginalPivotY, 0.0, 1.0);
    const double ExpectedPivotX = bOriginalPivotValid
        ? (OriginalPivotX * LogicalWidth + SourcePadding) / ExpandedWidth
        : 0.5;
    const double ExpectedPivotY = bOriginalPivotValid
        ? (OriginalPivotY * LogicalHeight + SourcePadding) / ExpandedHeight
        : 0.5;
    if (!LayoutAdjustment
        || LayoutAdjustment->Values.Num() != 6
        || !JsonVectorEquals(OriginalSize, LogicalWidth, LogicalHeight)
        || !JsonVectorEquals(ExpandedSize, ExpandedWidth, ExpandedHeight)
        || !bOriginalPivotValid
        || !JsonVectorEquals(ExpandedPivot, ExpectedPivotX, ExpectedPivotY)
        || !JsonVectorEquals(
            PositionPreserved,
            Layer.Position.X,
            Layer.Position.Y)
        || !LayoutAdjustment->TryGetNumberField(
            TEXT("rotation_degrees_preserved"),
            RotationPreserved)
        || !FMath::IsNearlyEqual(
            RotationPreserved,
            Layer.RotationDegrees,
            0.000001)
        || !Layer.RenderTransformPivot.Equals(
            FVector2D(ExpectedPivotX, ExpectedPivotY),
            0.000001)
        || !Layer.Anchor.Equals(
            FVector2D(ExpectedPivotX, ExpectedPivotY),
            0.000001)
        || !Layer.CanvasSlot.Alignment.Equals(
            FVector2D(ExpectedPivotX, ExpectedPivotY),
            0.000001)
        || !Layer.CanvasSlot.AnchorMinimum.Equals(
            Layer.CanvasSlot.AnchorMaximum,
            0.000001)
        || !FMath::IsNearlyEqual(
            Layer.CanvasSlot.Offsets.Right,
            ExpandedWidth,
            0.000001)
        || !FMath::IsNearlyEqual(
            Layer.CanvasSlot.Offsets.Bottom,
            ExpandedHeight,
            0.000001))
    {
        Reasons.Add(TEXT("baked_layout_adjustment_invalid"));
    }
    const TSharedPtr<FJsonObject> SubpathContract = RawObjectField(
        Source,
        TEXT("subpath_contract"));
    double SubpathCount = 0.0;
    double MaxSubpaths = 0.0;
    double BoundsEpsilon = 0.0;
    const TArray<TSharedPtr<FJsonValue>>* SubpathItems = nullptr;
    bool bSubpathsValid = bLogicalSizeValid
        && SubpathContract
        && HasRawIntegerField(SubpathContract, TEXT("count"))
        && SubpathContract->TryGetNumberField(
            TEXT("count"),
            SubpathCount)
        && SubpathCount >= 1.0
        && SubpathCount <= StaticVectorBakeMaxSubpaths
        && HasRawIntegerField(SubpathContract, TEXT("max_count"))
        && SubpathContract->TryGetNumberField(
            TEXT("max_count"),
            MaxSubpaths)
        && FMath::IsNearlyEqual(
            MaxSubpaths,
            static_cast<double>(StaticVectorBakeMaxSubpaths),
            0.000001)
        && SubpathContract->TryGetNumberField(
            TEXT("logical_bounds_epsilon"),
            BoundsEpsilon)
        && FMath::IsNearlyEqual(
            BoundsEpsilon,
            StaticVectorBakeBoundsEpsilon,
            0.000000001)
        && SubpathContract->TryGetArrayField(
            TEXT("items"),
            SubpathItems)
        && SubpathItems
        && SubpathItems->Num() == FMath::RoundToInt(SubpathCount)
        && ActualSubpathIndices.Num() == FMath::RoundToInt(SubpathCount);
    if (bSubpathsValid)
    {
        for (int32 ItemIndex = 0; ItemIndex < SubpathItems->Num(); ++ItemIndex)
        {
            const TSharedPtr<FJsonValue>& ItemValue = (*SubpathItems)[ItemIndex];
            const TSharedPtr<FJsonObject> Item =
                ItemValue && ItemValue->Type == EJson::Object
                ? ItemValue->AsObject()
                : nullptr;
            const TSharedPtr<FJsonObject> Bounds = RawObjectField(
                Item,
                TEXT("bounds"));
            double Index = -1.0;
            double RowIndex = -1.0;
            double LocalIndex = -1.0;
            double X = 0.0;
            double Y = 0.0;
            double Width = 0.0;
            double Height = 0.0;
            bSubpathsValid = Item
                && HasRawIntegerField(Item, TEXT("index"))
                && Item->TryGetNumberField(TEXT("index"), Index)
                && FMath::RoundToInt(Index) == ItemIndex
                && HasRawIntegerField(Item, TEXT("row_index"))
                && Item->TryGetNumberField(TEXT("row_index"), RowIndex)
                && RowIndex >= 0.0
                && FMath::RoundToInt(RowIndex)
                    == ActualSubpathIndices[ItemIndex].X
                && HasRawIntegerField(Item, TEXT("subpath_index"))
                && Item->TryGetNumberField(
                    TEXT("subpath_index"),
                    LocalIndex)
                && LocalIndex >= 0.0
                && FMath::RoundToInt(LocalIndex)
                    == ActualSubpathIndices[ItemIndex].Y
                && Bounds
                && Bounds->TryGetNumberField(TEXT("x"), X)
                && Bounds->TryGetNumberField(TEXT("y"), Y)
                && Bounds->TryGetNumberField(TEXT("width"), Width)
                && Bounds->TryGetNumberField(TEXT("height"), Height)
                && FMath::IsFinite(X)
                && FMath::IsFinite(Y)
                && FMath::IsFinite(Width)
                && FMath::IsFinite(Height)
                && Width > StaticVectorBakeBoundsEpsilon
                && Height > StaticVectorBakeBoundsEpsilon
                && X >= -StaticVectorBakeBoundsEpsilon
                && Y >= -StaticVectorBakeBoundsEpsilon
                && X + Width
                    <= LogicalWidth + StaticVectorBakeBoundsEpsilon
                && Y + Height
                    <= LogicalHeight + StaticVectorBakeBoundsEpsilon;
            if (!bSubpathsValid)
            {
                break;
            }
        }
    }
    if (!bSubpathsValid)
    {
        Reasons.Add(TEXT("baked_static_vector_subpath_contract_invalid"));
    }

    const TSharedPtr<FJsonObject> GateTransition = RawObjectField(
        Bake,
        TEXT("gate_transition"));
    const TArray<TSharedPtr<FJsonValue>>* BeforeReasons = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* AfterReasons = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* SatisfiedReasons = nullptr;
    const bool bGateTransitionValid = GateTransition
        && GateTransition->TryGetArrayField(
            TEXT("before"),
            BeforeReasons)
        && BeforeReasons
        && BeforeReasons->Num() == 1
        && (*BeforeReasons)[0]
        && (*BeforeReasons)[0]->Type == EJson::String
        && (*BeforeReasons)[0]->AsString() == StaticVectorBakeGate
        && GateTransition->TryGetArrayField(
            TEXT("after"),
            AfterReasons)
        && AfterReasons
        && AfterReasons->IsEmpty()
        && GateTransition->TryGetArrayField(
            TEXT("satisfied"),
            SatisfiedReasons)
        && SatisfiedReasons
        && SatisfiedReasons->Num() == 1
        && (*SatisfiedReasons)[0]
        && (*SatisfiedReasons)[0]->Type == EJson::String
        && (*SatisfiedReasons)[0]->AsString() == StaticVectorBakeGate;
    if (!bGateTransitionValid)
    {
        Reasons.Add(TEXT("baked_static_vector_gate_transition_invalid"));
    }
    return Reasons;
}

TArray<FString> ValidateFlipbookLayer(
    const FTigerStudioUMGLayerRecord& Layer,
    const int32 SchemaVersion,
    const TMap<FString, FString>& ResourceKinds)
{
    TArray<FString> Reasons;
    const FTigerStudioUMGFlipbookRecord& Flipbook = Layer.Flipbook;
    if (Flipbook.AssetId.IsEmpty()
        && Flipbook.Schema.IsEmpty()
        && Flipbook.Generator.IsEmpty()
        && Flipbook.Kind.IsEmpty())
    {
        return Reasons;
    }

    if (SchemaVersion < 12)
    {
        Reasons.Add(TEXT("flipbook_requires_schema_12"));
    }
    if (Layer.Disposition != ETigerStudioUMGDisposition::Material)
    {
        Reasons.Add(TEXT("flipbook_requires_material_disposition"));
    }
    if (Layer.Kind != ETigerStudioUMGLayerKind::Image
        && Layer.Kind != ETigerStudioUMGLayerKind::Shape)
    {
        Reasons.Add(TEXT("flipbook_layer_kind_unsupported"));
    }
    if (!Layer.Material.Schema.IsEmpty()
        || !Layer.Material.Generator.IsEmpty()
        || !Layer.ImageFill.AssetId.IsEmpty())
    {
        Reasons.Add(TEXT("flipbook_conflicting_visual_record"));
    }
    if (Flipbook.Schema != TEXT("tigerstudio.umg.flipbook.v1"))
    {
        Reasons.Add(TEXT("flipbook_schema_unsupported"));
    }
    if (Flipbook.Generator
        != TEXT("tiger_ui_flipbook_atlas_custom_hlsl_v1"))
    {
        Reasons.Add(TEXT("flipbook_generator_unsupported"));
    }
    if (Flipbook.Kind != TEXT("FlipbookAtlas"))
    {
        Reasons.Add(TEXT("flipbook_kind_unsupported"));
    }
    if (Flipbook.CoordinateSpace != TEXT("LocalUV"))
    {
        Reasons.Add(TEXT("flipbook_coordinate_space_unsupported"));
    }
    if (Flipbook.AssetId.IsEmpty())
    {
        Reasons.Add(TEXT("flipbook_atlas_asset_id_missing"));
    }
    else if (const FString* ResourceKind = ResourceKinds.Find(
                 Flipbook.AssetId))
    {
        if (!ResourceKind->Equals(TEXT("texture"), ESearchCase::IgnoreCase)
            && !ResourceKind->Equals(TEXT("image"), ESearchCase::IgnoreCase))
        {
            Reasons.Add(TEXT("flipbook_atlas_resource_kind_unsupported"));
        }
    }
    else
    {
        Reasons.Add(TEXT("flipbook_atlas_resource_missing"));
    }

    constexpr int32 MaxColumns = 256;
    constexpr int32 MaxRows = 256;
    constexpr int32 MaxFrames = 4096;
    if (Flipbook.Columns < 1 || Flipbook.Columns > MaxColumns)
    {
        Reasons.Add(TEXT("flipbook_columns_out_of_range"));
    }
    if (Flipbook.Rows < 1 || Flipbook.Rows > MaxRows)
    {
        Reasons.Add(TEXT("flipbook_rows_out_of_range"));
    }
    const int64 Capacity = static_cast<int64>(Flipbook.Columns)
        * static_cast<int64>(Flipbook.Rows);
    if (Capacity > MaxFrames)
    {
        Reasons.Add(TEXT("flipbook_atlas_capacity_exceeded"));
    }
    if (Flipbook.FrameCount < 1
        || Flipbook.FrameCount > Capacity
        || Flipbook.FrameCount > MaxFrames)
    {
        Reasons.Add(TEXT("flipbook_frame_count_out_of_range"));
    }
    if (!FMath::IsFinite(Flipbook.FramesPerSecond)
        || Flipbook.FramesPerSecond < 0.0
        || Flipbook.FramesPerSecond > 240.0)
    {
        Reasons.Add(TEXT("flipbook_fps_out_of_range"));
    }
    if (Flipbook.StartFrame < 0
        || Flipbook.StartFrame >= Flipbook.FrameCount)
    {
        Reasons.Add(TEXT("flipbook_start_frame_out_of_range"));
    }
    if (!FMath::IsFinite(Flipbook.Phase)
        || Flipbook.Phase < 0.0
        || Flipbook.Phase > 1.0)
    {
        Reasons.Add(TEXT("flipbook_phase_out_of_range"));
    }
    if (Flipbook.StaticFrameOverride < -1
        || Flipbook.StaticFrameOverride >= Flipbook.FrameCount)
    {
        Reasons.Add(TEXT("flipbook_static_frame_override_out_of_range"));
    }
    return Reasons;
}

TArray<FString> ValidateMaterialLayer(
    const FTigerStudioUMGLayerRecord& Layer,
    const int32 SchemaVersion)
{
    TArray<FString> Reasons;
    const FTigerStudioUMGMaterialRecord& Material = Layer.Material;
    const bool bLegacyGradient =
        Material.Schema == TEXT("tigerstudio.umg.ui_material.v1");
    const bool bRoundedCard =
        Material.Schema == TEXT("tigerstudio.umg.ui_material.v2");
    if (!bLegacyGradient && !bRoundedCard)
    {
        Reasons.Add(TEXT("ui_material_schema_unsupported"));
        return Reasons;
    }

    if (Layer.Kind != ETigerStudioUMGLayerKind::Image
        && Layer.Kind != ETigerStudioUMGLayerKind::Shape)
    {
        Reasons.Add(TEXT("ui_material_layer_kind_unsupported"));
    }
    if (Material.CoordinateSpace != TEXT("LocalUV"))
    {
        Reasons.Add(TEXT("ui_material_coordinate_space_unsupported"));
    }

    if (bLegacyGradient)
    {
        if (Material.Generator != TEXT("tiger_ui_gradient_custom_hlsl_v1"))
        {
            Reasons.Add(TEXT("ui_material_generator_unsupported"));
        }
        if (Material.Kind != TEXT("LinearGradient")
            && Material.Kind != TEXT("RadialGradient"))
        {
            Reasons.Add(TEXT("ui_material_kind_unsupported"));
        }
        ValidateGradientStops(Material, Reasons);
        return Reasons;
    }

    if (SchemaVersion < 8)
    {
        Reasons.Add(TEXT("ui_material_requires_schema_8"));
    }
    if (Material.Generator
        != TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1"))
    {
        Reasons.Add(TEXT("ui_material_generator_unsupported"));
    }
    if (Material.Kind != TEXT("RoundedCard"))
    {
        Reasons.Add(TEXT("ui_material_kind_unsupported"));
    }
    const bool bValidSize = IsFiniteVector2D(Material.Size)
        && Material.Size.X > 0.0
        && Material.Size.Y > 0.0;
    if (!bValidSize)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_size_invalid"));
    }
    if (Material.SizeBinding != TEXT("FixedSize")
        && Material.SizeBinding != TEXT("WidgetGeometry"))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_size_binding_invalid"));
    }
    if (Material.SizeBinding == TEXT("WidgetGeometry")
        && SchemaVersion < DynamicRoundedCardSizeSchemaVersion)
    {
        Reasons.Add(
            TEXT("ui_material_dynamic_size_binding_requires_schema_19"));
    }

    const bool bSolidFill = Material.FillKind == TEXT("Solid");
    const bool bLinearFill = Material.FillKind == TEXT("LinearGradient");
    const bool bRadialFill = Material.FillKind == TEXT("RadialGradient");
    if (!bSolidFill && !bLinearFill && !bRadialFill)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_fill_kind_unsupported"));
    }
    if (!IsValidMaterialColor(Material.FillColor))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_fill_color_invalid"));
    }
    if (!FMath::IsFinite(Material.Opacity)
        || Material.Opacity < 0.0
        || Material.Opacity > 1.0)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_opacity_invalid"));
    }
    if (!IsFiniteVector2D(Material.Start)
        || !IsFiniteVector2D(Material.End)
        || !IsFiniteVector2D(Material.Width))
    {
        Reasons.Add(TEXT("ui_material_gradient_geometry_invalid"));
    }
    ValidateGradientStops(Material, Reasons);

    const FVector4& Radii = Material.CornerRadii;
    if (!FMath::IsFinite(Radii.X)
        || !FMath::IsFinite(Radii.Y)
        || !FMath::IsFinite(Radii.Z)
        || !FMath::IsFinite(Radii.W)
        || Radii.X < 0.0
        || Radii.Y < 0.0
        || Radii.Z < 0.0
        || Radii.W < 0.0)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_radii_invalid"));
    }
    else if (bValidSize
        && (Radii.X + Radii.Y > Material.Size.X + 0.000001
        || Radii.W + Radii.Z > Material.Size.X + 0.000001
        || Radii.X + Radii.W > Material.Size.Y + 0.000001
        || Radii.Y + Radii.Z > Material.Size.Y + 0.000001))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_radii_exceed_size"));
    }
    if (!FMath::IsFinite(Material.CornerSmoothing)
        || Material.CornerSmoothing < 0.0
        || Material.CornerSmoothing > 1.0)
    {
        Reasons.Add(TEXT("ui_material_rounded_card_smoothing_invalid"));
    }

    if (!FMath::IsFinite(Material.Stroke.Width)
        || Material.Stroke.Width < 0.0
        || (Material.Stroke.Alignment != TEXT("Inside")
            && Material.Stroke.Alignment != TEXT("Center")
            && Material.Stroke.Alignment != TEXT("Outside"))
        || !IsValidMaterialColor(Material.Stroke.Color))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_stroke_invalid"));
    }
    if (!IsValidShadow(Material.DropShadow))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_drop_shadow_invalid"));
    }
    if (!IsValidShadow(Material.InnerShadow))
    {
        Reasons.Add(TEXT("ui_material_rounded_card_inner_shadow_invalid"));
    }

    const FMargin& Padding = Material.VisualPadding;
    if (!FMath::IsFinite(Padding.Left)
        || !FMath::IsFinite(Padding.Top)
        || !FMath::IsFinite(Padding.Right)
        || !FMath::IsFinite(Padding.Bottom)
        || Padding.Left < 0.0
        || Padding.Top < 0.0
        || Padding.Right < 0.0
        || Padding.Bottom < 0.0)
    {
        Reasons.Add(TEXT("ui_material_visual_padding_invalid"));
    }
    else
    {
        const FMargin Expected = ExpectedVisualPadding(
            Material.Stroke,
            Material.DropShadow);
        if (!FMath::IsNearlyEqual(Padding.Left, Expected.Left, 0.0001)
            || !FMath::IsNearlyEqual(Padding.Top, Expected.Top, 0.0001)
            || !FMath::IsNearlyEqual(Padding.Right, Expected.Right, 0.0001)
            || !FMath::IsNearlyEqual(Padding.Bottom, Expected.Bottom, 0.0001))
        {
            Reasons.Add(TEXT("ui_material_visual_padding_invalid"));
        }
    }
    return Reasons;
}

bool ParseTypedJsonObject(
    const FString& Json,
    TSharedPtr<FJsonObject>& OutObject)
{
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    return FJsonSerializer::Deserialize(Reader, OutObject)
        && OutObject.IsValid();
}

void CollectTypedComponentSlotRootIds(
    const FTigerStudioUMGDocumentRecord& Document,
    TSet<FString>& OutRootIds)
{
    for (const FTigerStudioUMGComponentInstanceRecord& Instance
         : Document.ComponentInstances)
    {
        for (const FTigerStudioUMGComponentSlotContentRecord& SlotContent
             : Instance.SlotContents)
        {
            for (const FString& RootId : SlotContent.RootLayerIds)
            {
                if (!RootId.IsEmpty())
                {
                    OutRootIds.Add(RootId);
                }
            }
        }
    }

    // Nested component instances are serialized in their definition layer's
    // provider-neutral payload. Generation creates the same synthetic
    // UOverlay for these roots as it does for screen instances.
    for (const FTigerStudioUMGComponentRecord& Component : Document.Components)
    {
        for (const FTigerStudioUMGLayerRecord& Layer : Component.Layers)
        {
            TSharedPtr<FJsonObject> Payload;
            if (!ParseTypedJsonObject(Layer.PayloadJson, Payload))
            {
                continue;
            }
            const TSharedPtr<FJsonObject>* Instance = nullptr;
            const TArray<TSharedPtr<FJsonValue>>* SlotContents = nullptr;
            if (!Payload->TryGetObjectField(TEXT("component_instance"), Instance)
                || !Instance || !Instance->IsValid()
                || !(*Instance)->TryGetArrayField(
                    TEXT("slot_contents"),
                    SlotContents)
                || !SlotContents)
            {
                continue;
            }
            for (const TSharedPtr<FJsonValue>& SlotValue : *SlotContents)
            {
                const TSharedPtr<FJsonObject> Slot = SlotValue
                    && SlotValue->Type == EJson::Object
                    ? SlotValue->AsObject()
                    : nullptr;
                const TArray<TSharedPtr<FJsonValue>>* RootValues = nullptr;
                if (!Slot
                    || (!Slot->TryGetArrayField(
                            TEXT("root_layer_ids"),
                            RootValues)
                        && !Slot->TryGetArrayField(
                            TEXT("RootLayerIds"),
                            RootValues))
                    || !RootValues)
                {
                    continue;
                }
                for (const TSharedPtr<FJsonValue>& RootValue : *RootValues)
                {
                    FString RootId;
                    if (RootValue
                        && RootValue->TryGetString(RootId)
                        && !RootId.IsEmpty())
                    {
                        OutRootIds.Add(RootId);
                    }
                }
            }
        }
    }
}

TSharedPtr<FJsonValue> ParseTypedJsonValue(const FString& Json)
{
    TSharedPtr<FJsonObject> Wrapper;
    const FString Wrapped = TEXT("{\"Value\":") + Json + TEXT("}");
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(Wrapped);
    if (!FJsonSerializer::Deserialize(Reader, Wrapper) || !Wrapper)
    {
        return nullptr;
    }
    return Wrapper->TryGetField(TEXT("Value"));
}

void ValidateComponentPropertyValues(
    const FString& OwnerId,
    const FTigerStudioUMGComponentRecord& Component,
    const TSharedPtr<FJsonObject>& Values,
    TArray<FString>& Reasons)
{
    if (!Values)
    {
        Reasons.Add(
            OwnerId + TEXT(":component_instance_property_values_json_invalid"));
        return;
    }
    TMap<FString, const FTigerStudioUMGComponentPropertyRecord*> Properties;
    for (const FTigerStudioUMGComponentPropertyRecord& Property
         : Component.Properties)
    {
        Properties.Add(Property.Name, &Property);
    }
    TSharedPtr<FJsonObject> Variants;
    ParseTypedJsonObject(Component.VariantValuesJson, Variants);
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Values->Values)
    {
        const FTigerStudioUMGComponentPropertyRecord* const* PropertyPtr =
            Properties.Find(Pair.Key);
        if (!PropertyPtr || !*PropertyPtr)
        {
            const TSharedPtr<FJsonValue> StaticVariant = Variants
                ? Variants->TryGetField(Pair.Key)
                : nullptr;
            if (!StaticVariant.IsValid())
            {
                Reasons.Add(
                    OwnerId + TEXT(":component_instance_property_unknown:")
                    + Pair.Key);
            }
            else if (!Pair.Value.IsValid()
                || !FJsonValue::CompareEqual(*StaticVariant, *Pair.Value))
            {
                Reasons.Add(
                    OwnerId + TEXT(":component_instance_variant_mismatch:")
                    + Pair.Key);
            }
            continue;
        }
        const FTigerStudioUMGComponentPropertyRecord& Property = **PropertyPtr;
        const FString Type = Property.Type.ToLower();
        bool bTypeValid = false;
        if (Type == TEXT("text") || Type == TEXT("slot"))
        {
            FString TextValue;
            bTypeValid = Pair.Value && Pair.Value->TryGetString(TextValue);
        }
        else if (Type == TEXT("boolean"))
        {
            bool bValue = false;
            bTypeValid = Pair.Value && Pair.Value->TryGetBool(bValue);
        }
        else if (Type == TEXT("enum"))
        {
            FString EnumValue;
            bTypeValid = Pair.Value
                && Pair.Value->TryGetString(EnumValue)
                && (Property.Values.IsEmpty()
                    || Property.Values.Contains(EnumValue));
        }
        if (!bTypeValid)
        {
            Reasons.Add(
                OwnerId + TEXT(":component_instance_property_type_mismatch:")
                + Property.Name);
        }
    }
}

void ValidateResolvedComponentOverrides(
    const FString& OwnerId,
    const TSharedPtr<FJsonObject>& Overrides,
    const TSet<FString>& DefinitionLayerIds,
    TArray<FString>& Reasons)
{
    if (!Overrides)
    {
        Reasons.Add(
            OwnerId + TEXT(":component_instance_overrides_json_invalid"));
        return;
    }
    for (const TPair<FString, TSharedPtr<FJsonValue>>& LayerPair
         : Overrides->Values)
    {
        if (!DefinitionLayerIds.Contains(LayerPair.Key))
        {
            Reasons.Add(
                OwnerId + TEXT(":component_instance_override_layer_missing:")
                + LayerPair.Key);
            continue;
        }
        const TSharedPtr<FJsonObject> Changes = LayerPair.Value
            ? LayerPair.Value->AsObject()
            : nullptr;
        if (!Changes)
        {
            Reasons.Add(
                OwnerId + TEXT(":component_instance_override_record_invalid"));
            continue;
        }
        for (const TPair<FString, TSharedPtr<FJsonValue>>& Change
             : Changes->Values)
        {
            bool bTypeValid = false;
            if (Change.Key == TEXT("content.text"))
            {
                FString TextValue;
                bTypeValid = Change.Value
                    && Change.Value->TryGetString(TextValue);
            }
            else if (Change.Key == TEXT("visible"))
            {
                bool bVisible = false;
                bTypeValid = Change.Value
                    && Change.Value->TryGetBool(bVisible);
            }
            else
            {
                Reasons.Add(
                    OwnerId
                    + TEXT(":component_instance_override_runtime_unsupported:")
                    + Change.Key);
                continue;
            }
            if (!bTypeValid)
            {
                Reasons.Add(
                    OwnerId + TEXT(":component_instance_override_type_invalid:")
                    + Change.Key);
            }
        }
    }
}

TSharedPtr<FJsonObject> TypedImplicitComponentDefaults(
    const FTigerStudioUMGComponentRecord& Component)
{
    TSharedPtr<FJsonObject> Expected = MakeShared<FJsonObject>();
    for (const FTigerStudioUMGComponentPropertyRecord& Property
         : Component.Properties)
    {
        const TSharedPtr<FJsonValue> DefaultValue =
            ParseTypedJsonValue(Property.DefaultValueJson);
        if (Property.Name.IsEmpty() || !DefaultValue)
        {
            return nullptr;
        }
        Expected->SetField(Property.Name, DefaultValue);
    }
    TSharedPtr<FJsonObject> Variants;
    if (!ParseTypedJsonObject(Component.VariantValuesJson, Variants))
    {
        return nullptr;
    }
    for (const auto& Pair : Variants->Values)
    {
        Expected->SetField(Pair.Key, Pair.Value);
    }
    return Expected;
}

TArray<FString> ValidateTypedComponentContract(
    const FTigerStudioUMGDocumentRecord& Document)
{
    TArray<FString> Reasons;
    if (Document.SchemaVersion < ComponentSchemaVersion)
    {
        if (!Document.Components.IsEmpty()
            || !Document.ComponentInstances.IsEmpty())
        {
            Reasons.Add(TEXT("umg_components_require_schema_18"));
        }
        return Reasons;
    }

    TSet<FString> ScreenLayerIds;
    TMap<FString, const FTigerStudioUMGLayerRecord*> ScreenLayersById;
    for (const FTigerStudioUMGLayerRecord& Layer : Document.Layers)
    {
        ScreenLayerIds.Add(Layer.Id);
        ScreenLayersById.Add(Layer.Id, &Layer);
    }

    TMap<FString, const FTigerStudioUMGComponentRecord*> ComponentsById;
    TMap<FString, TSet<FString>> LayerIdsByComponent;
    TMap<FString, TSet<FString>> SlotNamesByComponent;
    TSet<FString> AllDefinitionLayerIds;
    TMap<FString, FString> DefinitionOwnerByLayer;
    TMap<FString, FString> SafeComponentOwners;
    for (const FTigerStudioUMGComponentRecord& Component : Document.Components)
    {
        if (Component.Id.IsEmpty())
        {
            Reasons.Add(TEXT("umg_component_id_missing"));
            continue;
        }
        if (ComponentsById.Contains(Component.Id))
        {
            Reasons.Add(TEXT("umg_component_id_duplicate:") + Component.Id);
            continue;
        }
        ComponentsById.Add(Component.Id, &Component);
        const FString SafeName = SafeResourceObjectName(Component.Id);
        if (const FString* Owner = SafeComponentOwners.Find(SafeName))
        {
            Reasons.Add(FString::Printf(
                TEXT("component_asset_name_collision:%s:%s:%s"),
                *SafeName,
                **Owner,
                *Component.Id));
        }
        else
        {
            SafeComponentOwners.Add(SafeName, Component.Id);
        }

        TSet<FString>& LocalLayerIds =
            LayerIdsByComponent.FindOrAdd(Component.Id);
        for (const FTigerStudioUMGLayerRecord& Layer : Component.Layers)
        {
            if (Layer.Id.IsEmpty())
            {
                Reasons.Add(
                    Component.Id + TEXT(":umg_component_layer_id_missing"));
            }
            else if (LocalLayerIds.Contains(Layer.Id))
            {
                Reasons.Add(
                    Component.Id + TEXT(":umg_component_layer_id_duplicate:")
                    + Layer.Id);
            }
            else if (AllDefinitionLayerIds.Contains(Layer.Id))
            {
                Reasons.Add(
                    Layer.Id
                    + TEXT(":umg_component_layer_owned_by_multiple_definitions"));
            }
            LocalLayerIds.Add(Layer.Id);
            AllDefinitionLayerIds.Add(Layer.Id);
            if (!Layer.Id.IsEmpty()
                && !DefinitionOwnerByLayer.Contains(Layer.Id))
            {
                DefinitionOwnerByLayer.Add(Layer.Id, Component.Id);
            }
            if (Layer.Kind == ETigerStudioUMGLayerKind::Group
                && Layer.ScrollOverflow != TEXT("None"))
            {
                Reasons.Add(
                    Layer.Id
                    + TEXT(":component_group_scroll_runtime_unsupported"));
            }
            if (Layer.Kind == ETigerStudioUMGLayerKind::Group
                && !Layer.ImageFill.AssetId.IsEmpty())
            {
                Reasons.Add(
                    Layer.Id
                    + TEXT(":component_group_image_fill_runtime_unsupported"));
            }
            if (Layer.Kind == ETigerStudioUMGLayerKind::Group
                && Layer.SpacingStrategy == TEXT("Spacer"))
            {
                Reasons.Add(
                    Layer.Id
                    + TEXT(":component_group_spacer_runtime_unsupported"));
            }
            if (Layer.Kind == ETigerStudioUMGLayerKind::Button
                && !Layer.ImageFill.AssetId.IsEmpty())
            {
                Reasons.Add(
                    Layer.Id
                    + TEXT(":component_button_image_fill_runtime_unsupported"));
            }
            if (!Layer.AssetId.IsEmpty()
                && Layer.ImageFill.AssetId.IsEmpty()
                && Layer.Disposition == ETigerStudioUMGDisposition::Native)
            {
                Reasons.Add(
                    Layer.Id
                    + TEXT(":component_legacy_asset_runtime_unsupported"));
            }
        }
        if (!LocalLayerIds.Contains(Component.RootLayerId))
        {
            Reasons.Add(
                Component.Id + TEXT(":umg_component_root_layer_missing"));
        }
        TSharedPtr<FJsonObject> VariantValues;
        if (!ParseTypedJsonObject(Component.VariantValuesJson, VariantValues))
        {
            Reasons.Add(
                Component.Id
                + TEXT(":umg_component_variant_values_json_invalid"));
        }

        TSet<FString> PropertyNames;
        TMap<FName, FString> SafePropertyOwners;
        for (const FTigerStudioUMGComponentPropertyRecord& Property
             : Component.Properties)
        {
            if (Property.Name.IsEmpty())
            {
                Reasons.Add(
                    Component.Id + TEXT(":umg_component_property_name_missing"));
            }
            else if (PropertyNames.Contains(Property.Name))
            {
                Reasons.Add(
                    Component.Id + TEXT(":umg_component_property_name_duplicate:")
                    + Property.Name);
            }
            PropertyNames.Add(Property.Name);
            const FName SafeProperty(*SafeResourceObjectName(Property.Name));
            if (const FString* Owner = SafePropertyOwners.Find(SafeProperty))
            {
                Reasons.Add(FString::Printf(
                    TEXT("%s:component_property_name_collision:%s:%s"),
                    *Component.Id,
                    **Owner,
                    *Property.Name));
            }
            else
            {
                SafePropertyOwners.Add(SafeProperty, Property.Name);
            }
            const FString Type = Property.Type.ToLower();
            if (Type == TEXT("number") || Type == TEXT("instance_swap"))
            {
                Reasons.Add(
                    TEXT("umg_component_property_runtime_unsupported:")
                    + Type);
            }
            else if (Type != TEXT("text")
                && Type != TEXT("boolean")
                && Type != TEXT("enum")
                && Type != TEXT("slot"))
            {
                Reasons.Add(
                    Component.Id + TEXT(":umg_component_property_type_invalid:")
                    + Type);
            }
            const TSharedPtr<FJsonValue> DefaultValue =
                ParseTypedJsonValue(Property.DefaultValueJson);
            bool bDefaultValid = false;
            if (Type == TEXT("text") || Type == TEXT("slot"))
            {
                FString TextValue;
                bDefaultValid = DefaultValue
                    && DefaultValue->TryGetString(TextValue);
            }
            else if (Type == TEXT("boolean"))
            {
                bool bValue = false;
                bDefaultValid = DefaultValue
                    && DefaultValue->TryGetBool(bValue);
            }
            else if (Type == TEXT("enum"))
            {
                FString EnumValue;
                bDefaultValid = DefaultValue
                    && DefaultValue->TryGetString(EnumValue)
                    && (Property.Values.IsEmpty()
                        || Property.Values.Contains(EnumValue));
            }
            if (!bDefaultValid
                && Type != TEXT("number")
                && Type != TEXT("instance_swap"))
            {
                Reasons.Add(
                    Component.Id
                    + TEXT(":umg_component_property_default_invalid:")
                    + Property.Name);
            }
            for (const FTigerStudioUMGComponentPropertyBindingRecord& Binding
                 : Property.Bindings)
            {
                if (!LocalLayerIds.Contains(Binding.LayerId))
                {
                    Reasons.Add(
                        Component.Id
                        + TEXT(":umg_component_property_binding_layer_missing:")
                        + Binding.LayerId);
                }
                const bool bSupported =
                    (Type == TEXT("text")
                        && Binding.TargetPath == TEXT("content.text"))
                    || (Type == TEXT("boolean")
                        && Binding.TargetPath == TEXT("visible"));
                if (!bSupported)
                {
                    Reasons.Add(FString::Printf(
                        TEXT("%s:component_property_binding_runtime_unsupported:%s:%s"),
                        *Component.Id,
                        *Type,
                        *Binding.TargetPath));
                }
            }
        }

        TSet<FString>& SlotNames =
            SlotNamesByComponent.FindOrAdd(Component.Id);
        TSet<FString> SafeSlotNames;
        for (const FTigerStudioUMGComponentSlotRecord& Slot : Component.Slots)
        {
            if (Slot.Name.IsEmpty() || SlotNames.Contains(Slot.Name))
            {
                Reasons.Add(
                    Component.Id + TEXT(":umg_component_slot_name_invalid:")
                    + Slot.Name);
            }
            SlotNames.Add(Slot.Name);
            const FString SafeSlotName = SafeResourceObjectName(Slot.Name);
            if (SafeSlotNames.Contains(SafeSlotName))
            {
                Reasons.Add(
                    Component.Id + TEXT(":component_slot_name_collision:")
                    + SafeSlotName);
            }
            SafeSlotNames.Add(SafeSlotName);
            if (!LocalLayerIds.Contains(Slot.LayerId))
            {
                Reasons.Add(
                    Component.Id + TEXT(":umg_component_slot_layer_missing:")
                    + Slot.LayerId);
            }
        }
    }
    TMap<FString, uint8> VisitState;
    TFunction<void(const FString&)> Visit = [&](const FString& ComponentId)
    {
        if (VisitState.FindRef(ComponentId) == 2)
        {
            return;
        }
        if (VisitState.FindRef(ComponentId) == 1)
        {
            Reasons.Add(TEXT("umg_component_dependency_cycle:") + ComponentId);
            return;
        }
        const FTigerStudioUMGComponentRecord* const* Component =
            ComponentsById.Find(ComponentId);
        if (!Component || !*Component)
        {
            return;
        }
        VisitState.Add(ComponentId, 1);
        if (!(*Component)->BaseComponentId.IsEmpty()
            && !ComponentsById.Contains((*Component)->BaseComponentId))
        {
            Reasons.Add(
                ComponentId + TEXT(":umg_component_base_missing:")
                + (*Component)->BaseComponentId);
        }
        for (const FString& Dependency : (*Component)->DependencyComponentIds)
        {
            if (!ComponentsById.Contains(Dependency))
            {
                Reasons.Add(
                    ComponentId + TEXT(":umg_component_dependency_missing:")
                    + Dependency);
            }
            else
            {
                Visit(Dependency);
            }
        }
        VisitState.Add(ComponentId, 2);
    };
    for (const TPair<FString, const FTigerStudioUMGComponentRecord*>& Pair
         : ComponentsById)
    {
        Visit(Pair.Key);
    }

    for (const FTigerStudioUMGComponentRecord& OwnerComponent
         : Document.Components)
    {
        const TSet<FString>& OwnerLayerIds =
            LayerIdsByComponent.FindRef(OwnerComponent.Id);
        for (const FTigerStudioUMGLayerRecord& Layer : OwnerComponent.Layers)
        {
            TSharedPtr<FJsonObject> Payload;
            if (!ParseTypedJsonObject(Layer.PayloadJson, Payload))
            {
                Reasons.Add(
                    Layer.Id + TEXT(":component_layer_payload_json_invalid"));
                continue;
            }
            const TSharedPtr<FJsonObject>* Instance = nullptr;
            if (!Payload->TryGetObjectField(
                    TEXT("component_instance"),
                    Instance))
            {
                continue;
            }
            if (!Instance || !Instance->IsValid())
            {
                Reasons.Add(
                    Layer.Id + TEXT(":component_instance_payload_invalid"));
                continue;
            }
            FString InstanceId;
            FString ChildComponentId;
            const TSharedPtr<FJsonObject>* PropertyValues = nullptr;
            const TSharedPtr<FJsonObject>* Overrides = nullptr;
            const TArray<TSharedPtr<FJsonValue>>* SlotContents = nullptr;
            if (!(*Instance)->TryGetStringField(TEXT("id"), InstanceId)
                || InstanceId != Layer.Id
                || !(*Instance)->TryGetStringField(
                    TEXT("component_id"),
                    ChildComponentId)
                || ChildComponentId.IsEmpty()
                || !(*Instance)->TryGetObjectField(
                    TEXT("property_values"),
                    PropertyValues)
                || !PropertyValues || !PropertyValues->IsValid()
                || !(*Instance)->TryGetObjectField(
                    TEXT("resolved_overrides"),
                    Overrides)
                || !Overrides || !Overrides->IsValid()
                || !(*Instance)->TryGetArrayField(
                    TEXT("slot_contents"),
                    SlotContents)
                || !SlotContents)
            {
                Reasons.Add(
                    Layer.Id + TEXT(":component_instance_payload_invalid"));
                continue;
            }
            if (Layer.Disposition != ETigerStudioUMGDisposition::Native)
            {
                Reasons.Add(
                    Layer.Id
                    + TEXT(":component_instance_disposition_must_be_native"));
            }
            if (!OwnerComponent.DependencyComponentIds.Contains(
                    ChildComponentId))
            {
                Reasons.Add(
                    Layer.Id + TEXT(":component_dependency_not_declared:")
                    + ChildComponentId);
            }
            const FTigerStudioUMGComponentRecord* const* ChildComponent =
                ComponentsById.Find(ChildComponentId);
            if (!ChildComponent || !*ChildComponent)
            {
                Reasons.Add(
                    Layer.Id + TEXT(":component_dependency_missing:")
                    + ChildComponentId);
                continue;
            }
            ValidateComponentPropertyValues(
                Layer.Id,
                **ChildComponent,
                *PropertyValues,
                Reasons);
            ValidateResolvedComponentOverrides(
                Layer.Id,
                *Overrides,
                LayerIdsByComponent.FindRef(ChildComponentId),
                Reasons);
            TSet<FString> SeenSlots;
            for (const TSharedPtr<FJsonValue>& SlotContentValue
                 : *SlotContents)
            {
                const TSharedPtr<FJsonObject> SlotContent =
                    SlotContentValue
                        && SlotContentValue->Type == EJson::Object
                    ? SlotContentValue->AsObject()
                    : nullptr;
                FString SlotName;
                const TArray<TSharedPtr<FJsonValue>>* RootValues = nullptr;
                const bool bHasSlotName = SlotContent
                    && (SlotContent->TryGetStringField(
                            TEXT("slot_name"),
                            SlotName)
                        || SlotContent->TryGetStringField(
                            TEXT("SlotName"),
                            SlotName));
                const bool bHasRoots = SlotContent
                    && (SlotContent->TryGetArrayField(
                            TEXT("root_layer_ids"),
                            RootValues)
                        || SlotContent->TryGetArrayField(
                            TEXT("RootLayerIds"),
                            RootValues));
                if (!bHasSlotName || SlotName.IsEmpty()
                    || !bHasRoots || !RootValues)
                {
                    Reasons.Add(
                        Layer.Id
                        + TEXT(":component_instance_slot_content_record_invalid"));
                    continue;
                }
                if (!SlotNamesByComponent.FindRef(ChildComponentId).Contains(
                        SlotName))
                {
                    Reasons.Add(
                        Layer.Id + TEXT(":component_instance_slot_missing:")
                        + SlotName);
                }
                if (SeenSlots.Contains(SlotName))
                {
                    Reasons.Add(
                        Layer.Id
                        + TEXT(":component_instance_slot_content_duplicate:")
                        + SlotName);
                }
                SeenSlots.Add(SlotName);
                for (const TSharedPtr<FJsonValue>& RootValue : *RootValues)
                {
                    FString RootId;
                    if (!RootValue || !RootValue->TryGetString(RootId)
                        || !OwnerLayerIds.Contains(RootId))
                    {
                        Reasons.Add(
                            Layer.Id
                            + TEXT(":component_instance_slot_root_missing"));
                    }
                }
            }
        }
    }

    TSet<FString> InstanceIds;
    TSet<FString> ImplicitDefinitionPlacementIds;
    for (const FTigerStudioUMGComponentInstanceRecord& Instance
         : Document.ComponentInstances)
    {
        const FTigerStudioUMGComponentRecord* const* Component =
            ComponentsById.Find(Instance.ComponentId);
        const FTigerStudioUMGLayerRecord* const* Layer =
            ScreenLayersById.Find(Instance.LayerId);
        if (Instance.Id.IsEmpty() || InstanceIds.Contains(Instance.Id))
        {
            Reasons.Add(
                Instance.Id.IsEmpty()
                    ? TEXT("umg_component_instance_id_missing")
                    : Instance.Id
                        + TEXT(":umg_component_instance_id_duplicate"));
        }
        InstanceIds.Add(Instance.Id);
        if (Instance.Id != Instance.LayerId)
        {
            Reasons.Add(
                Instance.Id
                + TEXT(":umg_component_instance_stable_id_mismatch"));
        }
        if (!Component || !*Component)
        {
            Reasons.Add(
                Instance.Id
                + TEXT(":umg_component_instance_component_missing"));
            continue;
        }
        const bool bImplicitDefinitionPlacement =
            Layer && *Layer
            && Instance.Id == Instance.LayerId
            && Instance.LayerId == (*Component)->RootLayerId
            && DefinitionOwnerByLayer.FindRef(Instance.LayerId)
                == Instance.ComponentId;
        if (bImplicitDefinitionPlacement)
        {
            ImplicitDefinitionPlacementIds.Add(Instance.LayerId);
        }
        if (!Layer || !*Layer)
        {
            Reasons.Add(
                Instance.Id + TEXT(":umg_component_instance_layer_missing"));
        }
        else if ((*Layer)->Disposition != ETigerStudioUMGDisposition::Native)
        {
            Reasons.Add(
                Instance.Id
                + TEXT(":component_instance_disposition_must_be_native"));
        }
        else if ((*Layer)->ParentId != Instance.ParentId)
        {
            Reasons.Add(
                Instance.Id
                + TEXT(":umg_component_instance_parent_mismatch"));
        }
        TSharedPtr<FJsonObject> PropertyValues;
        if (!ParseTypedJsonObject(
                Instance.PropertyValuesJson,
                PropertyValues))
        {
            Reasons.Add(
                Instance.Id
                + TEXT(":umg_component_instance_property_values_json_invalid"));
        }
        else
        {
            ValidateComponentPropertyValues(
                Instance.Id,
                **Component,
                PropertyValues,
                Reasons);
            if (bImplicitDefinitionPlacement)
            {
                const TSharedPtr<FJsonObject> Expected =
                    TypedImplicitComponentDefaults(**Component);
                if (Expected
                    && !JsonObjectsEqualExact(Expected, PropertyValues))
                {
                    Reasons.AddUnique(
                        TEXT("umg_implicit_component_property_values_not_default"));
                }
            }
        }
        TSharedPtr<FJsonObject> Overrides;
        ParseTypedJsonObject(Instance.ResolvedOverridesJson, Overrides);
        ValidateResolvedComponentOverrides(
            Instance.Id,
            Overrides,
            LayerIdsByComponent.FindRef(Instance.ComponentId),
            Reasons);
        TSet<FString> SeenSlots;
        for (const FTigerStudioUMGComponentSlotContentRecord& SlotContent
             : Instance.SlotContents)
        {
            if (!SlotNamesByComponent.FindRef(Instance.ComponentId).Contains(
                    SlotContent.SlotName))
            {
                Reasons.Add(
                    Instance.Id + TEXT(":umg_component_instance_slot_missing:")
                    + SlotContent.SlotName);
            }
            if (SeenSlots.Contains(SlotContent.SlotName))
            {
                Reasons.Add(
                    Instance.Id
                    + TEXT(":umg_component_instance_slot_content_duplicate:")
                    + SlotContent.SlotName);
            }
            SeenSlots.Add(SlotContent.SlotName);
            for (const FString& RootId : SlotContent.RootLayerIds)
            {
                if (!ScreenLayerIds.Contains(RootId))
                {
                    Reasons.Add(
                        Instance.Id
                        + TEXT(":umg_component_instance_slot_root_missing:")
                        + RootId);
                }
            }
        }
    }

    for (const FString& DefinitionLayerId : AllDefinitionLayerIds)
    {
        if (ScreenLayerIds.Contains(DefinitionLayerId)
            && !ImplicitDefinitionPlacementIds.Contains(DefinitionLayerId))
        {
            Reasons.AddUnique(
                TEXT("umg_component_definition_layer_leaked_to_screen"));
            break;
        }
    }

    TMap<FString, FString> ComponentOwnerByLayer;
    for (const TPair<FString, TSet<FString>>& Pair : LayerIdsByComponent)
    {
        for (const FString& LayerId : Pair.Value)
        {
            ComponentOwnerByLayer.Add(LayerId, Pair.Key);
        }
    }
    for (const FTigerStudioUMGInteractionRecord& Interaction
         : Document.Interactions)
    {
        const FString* Owner =
            ComponentOwnerByLayer.Find(Interaction.ComponentId);
        if (!Owner)
        {
            continue;
        }
        for (const FTigerStudioUMGActionRecord& Action : Interaction.Actions)
        {
            if (Action.Type.Equals(
                    TEXT("play_animation"),
                    ESearchCase::IgnoreCase))
            {
                Reasons.Add(
                    Interaction.ComponentId
                    + TEXT(":component_animation_interaction_runtime_unsupported"));
            }
            if (!Action.TargetId.IsEmpty()
                && ComponentOwnerByLayer.FindRef(Action.TargetId) != *Owner)
            {
                Reasons.Add(
                    Interaction.ComponentId
                    + TEXT(":component_interaction_target_outside_definition:")
                    + Action.TargetId);
            }
        }
    }
    return Reasons;
}
}

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

    TSharedPtr<FJsonObject> DocumentObject;
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, DocumentObject)
        || !DocumentObject)
    {
        Result.Message = TEXT("Could not parse Tiger UMG document JSON.");
        return Result;
    }

    int32 SerializedSchemaVersion = 0;
    DocumentObject->TryGetNumberField(
        TEXT("SchemaVersion"),
        SerializedSchemaVersion);
    if (SerializedSchemaVersion < 4 || SerializedSchemaVersion > 19)
    {
        Result.Message = FString::Printf(
            TEXT("Unsupported Tiger UMG schema version: %d"),
            SerializedSchemaVersion);
        return Result;
    }
    const TArray<FString> RawComponentBlockReasons =
        ValidateRawComponentRecords(
            DocumentObject,
            SerializedSchemaVersion);
    if (!RawComponentBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawComponentBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid component record(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TSharedPtr<FJsonObject> LayerValidationDocument =
        RawLayerValidationDocument(
            DocumentObject,
            SerializedSchemaVersion);
    const TArray<FString> RawDocumentRecordBlockReasons =
        ValidateRawDocumentRecords(LayerValidationDocument);
    if (!RawDocumentRecordBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawDocumentRecordBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid document record(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TArray<FString> RawVisibilityBlockReasons =
        ValidateRawLayerVisibility(
            LayerValidationDocument,
            SerializedSchemaVersion);
    if (!RawVisibilityBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawVisibilityBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid layer visibility: %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TArray<FString> RawPanelBlockReasons =
        ValidateRawPanelRecords(
            LayerValidationDocument,
            SerializedSchemaVersion);
    if (!RawPanelBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawPanelBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid panel record(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TArray<FString> RawButtonStyleBlockReasons =
        ValidateRawButtonStyleLayers(
            LayerValidationDocument,
            SerializedSchemaVersion);
    if (!RawButtonStyleBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawButtonStyleBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid ButtonStyle layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TArray<FString> RawV2BlockReasons =
        ValidateRawV2MaterialLayers(
            LayerValidationDocument,
            SerializedSchemaVersion);
    if (!RawV2BlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawV2BlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by unsupported generation layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TArray<FString> RawImageFillBlockReasons =
        ValidateRawImageFillLayers(
            LayerValidationDocument,
            SerializedSchemaVersion);
    if (!RawImageFillBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawImageFillBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid Image Fill layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TArray<FString> RawFlipbookBlockReasons =
        ValidateRawFlipbookLayers(
            LayerValidationDocument,
            SerializedSchemaVersion);
    if (!RawFlipbookBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawFlipbookBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid Flipbook layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    const TArray<FString> RawBakedBlockReasons =
        ValidateRawMaterializedBakedLayers(
            LayerValidationDocument,
            SerializedSchemaVersion);
    if (!RawBakedBlockReasons.IsEmpty())
    {
        Result.BlockReasons = RawBakedBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid Baked layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }
    if (SerializedSchemaVersion == 4)
    {
        AddV5DefaultsToV4Layers(DocumentObject);
    }
    AddLegacyLayerDefaults(DocumentObject, SerializedSchemaVersion);
    AddLegacyComponentDocumentDefaults(
        DocumentObject,
        SerializedSchemaVersion);
    AddV2DefaultsToLegacyMaterials(DocumentObject);
    AddV2DefaultsToLegacyComponentMaterials(DocumentObject);
    AddMaterialSizeBindingDefaults(DocumentObject);

    FText FailureReason;
    if (!FJsonObjectConverter::JsonObjectToUStruct(
            DocumentObject.ToSharedRef(),
            &Result.Document,
            0,
            0,
            true,
            &FailureReason))
    {
        Result.Message = FailureReason.ToString();
        return Result;
    }

    if (Result.Document.SchemaVersion < 4
        || Result.Document.SchemaVersion > 19)
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
    const TArray<FString> TypedComponentBlockReasons =
        ValidateTypedComponentContract(Result.Document);
    if (!TypedComponentBlockReasons.IsEmpty())
    {
        Result.BlockReasons = TypedComponentBlockReasons;
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by invalid component contract: %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }

    Result.ResourceCount = Result.Document.Resources.Num();
    Result.InteractionCount = Result.Document.Interactions.Num();
    TSet<FString> ResourceIds;
    TSet<FString> ResourceDestinationKeys;
    TMap<FString, FString> ResourceKinds;
    TMap<FString, FTigerStudioUMGResourceRecord> ResourcesById;
    TMap<FString, FString> ResourceFileHashes;
    TMap<FString, FString> ResourceSourcePaths;
    const FString DocumentDirectory = FPaths::GetPath(DocumentPath);
    for (const FTigerStudioUMGResourceRecord& Resource : Result.Document.Resources)
    {
        if (Resource.Id.IsEmpty() || ResourceIds.Contains(Resource.Id))
        {
            Result.Message = TEXT("Resource IDs must be non-empty and unique.");
            return Result;
        }
        ResourceIds.Add(Resource.Id);
        ResourceKinds.Add(Resource.Id, Resource.Kind);
        ResourcesById.Add(Resource.Id, Resource);
        const FString DestinationKey = (
            ResourceFolder(Resource.Kind)
            + TEXT("/")
            + SafeResourceObjectName(Resource.DestinationName)).ToLower();
        if (ResourceDestinationKeys.Contains(DestinationKey))
        {
            Result.Message = TEXT(
                "Resource destination object paths must be unique after normalization.");
            Result.BlockReasons.Add(
                Resource.Id + TEXT(":umg_resource_destination_collision"));
            return Result;
        }
        ResourceDestinationKeys.Add(DestinationKey);
        if (FPaths::IsRelative(Resource.SourcePath)
            && !IsSafeRelativeArtifactPath(
                Resource.SourcePath,
                FPaths::GetExtension(Resource.SourcePath)))
        {
            Result.Message = FString::Printf(
                TEXT("Resource relative path is unsafe: %s"),
                *Resource.SourcePath);
            Result.BlockReasons.Add(
                Resource.Id + TEXT(":umg_resource_source_path_invalid"));
            return Result;
        }
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
        FString ActualHash;
        if (!HashFileSha256(SourcePath, ActualHash))
        {
            Result.Message = FString::Printf(
                TEXT("Resource file could not be hashed: %s"),
                *SourcePath);
            return Result;
        }
        ResourceFileHashes.Add(Resource.Id, ActualHash);
        ResourceSourcePaths.Add(Resource.Id, SourcePath);
    }

    TMap<FString, FString> ParentPanelKinds;
    TMap<FString, FString> ParentSpacingStrategies;
    TMap<FString, FString> ParentScrollOverflow;
    TSet<FString> SyntheticOverlayRootIds;
    CollectTypedComponentSlotRootIds(
        Result.Document,
        SyntheticOverlayRootIds);
    TArray<const FTigerStudioUMGLayerRecord*> ValidatedLayers;
    for (const FTigerStudioUMGLayerRecord& Layer : Result.Document.Layers)
    {
        ValidatedLayers.Add(&Layer);
    }
    for (const FTigerStudioUMGComponentRecord& Component
         : Result.Document.Components)
    {
        for (const FTigerStudioUMGLayerRecord& Layer : Component.Layers)
        {
            ValidatedLayers.Add(&Layer);
        }
    }
    for (const FTigerStudioUMGLayerRecord* LayerPtr : ValidatedLayers)
    {
        const FTigerStudioUMGLayerRecord& Layer = *LayerPtr;
        if (Layer.Kind != ETigerStudioUMGLayerKind::Group)
        {
            continue;
        }
        ParentPanelKinds.Add(
            Layer.Id,
            (Layer.PanelKind.IsEmpty() || Layer.PanelKind == TEXT("None"))
                ? TEXT("Canvas")
                : Layer.PanelKind);
        ParentSpacingStrategies.Add(
            Layer.Id,
            Layer.SpacingStrategy.IsEmpty()
                ? TEXT("Padding")
                : Layer.SpacingStrategy);
        ParentScrollOverflow.Add(
            Layer.Id,
            Layer.ScrollOverflow.IsEmpty()
                ? TEXT("None")
                : Layer.ScrollOverflow);
    }

    for (const FTigerStudioUMGLayerRecord* LayerPtr : ValidatedLayers)
    {
        const FTigerStudioUMGLayerRecord& Layer = *LayerPtr;
        const FString* ParentSpacingStrategy =
            ParentSpacingStrategies.Find(Layer.ParentId);
        const FString* ParentPanelKind =
            ParentPanelKinds.Find(Layer.ParentId);
        if (ParentSpacingStrategy
            && *ParentSpacingStrategy == TEXT("Spacer")
            && ParentPanelKind)
        {
            const bool bNegativeLinearSpacing =
                (*ParentPanelKind == TEXT("Horizontal")
                    && (Layer.FlowSlot.Padding.Left < 0.0
                        || Layer.FlowSlot.Padding.Right < 0.0))
                || (*ParentPanelKind == TEXT("Vertical")
                    && (Layer.FlowSlot.Padding.Top < 0.0
                        || Layer.FlowSlot.Padding.Bottom < 0.0));
            if (bNegativeLinearSpacing)
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_spacer_size_must_be_nonnegative"));
            }
        }
        if (Result.Document.SchemaVersion < LayerVisibilitySchemaVersion
            && Layer.Visibility != TEXT("Visible"))
        {
            Result.BlockReasons.Add(
                Layer.Id
                + TEXT(":umg_visibility_requires_schema_16"));
        }
        else if (Layer.Visibility != TEXT("Visible")
            && Layer.Visibility != TEXT("HitTestInvisible"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_visibility_unsupported"));
        }
        for (const FString& Reason : ValidateButtonStyleLayer(
                 Layer,
                 Result.Document.SchemaVersion))
        {
            Result.BlockReasons.Add(Layer.Id + TEXT(":") + Reason);
        }
        if (Layer.Disposition == ETigerStudioUMGDisposition::Native)
        {
            for (const FString& Reason : ValidateImageFillLayer(
                     Layer,
                     Result.Document.SchemaVersion,
                     ResourceKinds,
                     ParentPanelKinds,
                     SyntheticOverlayRootIds))
            {
                Result.BlockReasons.Add(Layer.Id + TEXT(":") + Reason);
            }
            for (const FString& Reason : ValidateFlipbookLayer(
                     Layer,
                     Result.Document.SchemaVersion,
                     ResourceKinds))
            {
                Result.BlockReasons.Add(Layer.Id + TEXT(":") + Reason);
            }
        }
        const FString ScrollOverflow = Layer.ScrollOverflow.IsEmpty()
            ? TEXT("None")
            : Layer.ScrollOverflow;
        const FString ScrollPosition = Layer.ScrollPosition.IsEmpty()
            ? TEXT("Scroll")
            : Layer.ScrollPosition;
        if (ScrollOverflow != TEXT("None")
            && ScrollOverflow != TEXT("Horizontal")
            && ScrollOverflow != TEXT("Vertical")
            && ScrollOverflow != TEXT("Both"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_scroll_overflow_unsupported:")
                + ScrollOverflow);
        }
        if (ScrollPosition != TEXT("Scroll")
            && ScrollPosition != TEXT("Fixed")
            && ScrollPosition != TEXT("Sticky"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_scroll_position_unsupported:")
                + ScrollPosition);
        }
        if (Result.Document.SchemaVersion < 10
            && (ScrollOverflow != TEXT("None")
                || ScrollPosition != TEXT("Scroll")))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_scroll_requires_schema_10"));
        }
        if (ScrollOverflow != TEXT("None")
            && Layer.Kind != ETigerStudioUMGLayerKind::Group)
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_scroll_overflow_requires_group"));
        }
        if (ScrollPosition == TEXT("Sticky"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_sticky_runtime_binding_unavailable"));
        }
        if (ScrollPosition == TEXT("Fixed"))
        {
            const FString* ParentOverflow =
                ParentScrollOverflow.Find(Layer.ParentId);
            if (!ParentOverflow || *ParentOverflow == TEXT("None"))
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_fixed_requires_scroll_parent"));
            }
        }
        const bool bIsGroup =
            Layer.Kind == ETigerStudioUMGLayerKind::Group;
        const FString SpacingStrategy = Layer.SpacingStrategy.IsEmpty()
            ? TEXT("Padding")
            : Layer.SpacingStrategy;
        const FString SpacerSizeRule = Layer.SpacerSizeRule.IsEmpty()
            ? TEXT("Auto")
            : Layer.SpacerSizeRule;
        if (SpacingStrategy != TEXT("Padding")
            && SpacingStrategy != TEXT("Spacer"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_spacing_strategy_unsupported"));
        }
        if (SpacerSizeRule != TEXT("Auto")
            && SpacerSizeRule != TEXT("Fill"))
        {
            Result.BlockReasons.Add(
                Layer.Id + TEXT(":umg_spacer_size_rule_unsupported"));
        }
        if (!FMath::IsFinite(Layer.SpacerFillCoefficient)
            || Layer.SpacerFillCoefficient <= 0.0)
        {
            Result.BlockReasons.Add(
                Layer.Id
                + TEXT(":umg_spacer_fill_coefficient_invalid"));
        }
        if (Result.Document.SchemaVersion < SpacingStrategySchemaVersion
            && SpacingStrategy != TEXT("Padding"))
        {
            Result.BlockReasons.Add(
                Layer.Id
                + TEXT(":umg_spacing_strategy_requires_schema_17"));
        }
        if (!bIsGroup)
        {
            if (SpacingStrategy != TEXT("Padding"))
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + TEXT(
                        ":umg_non_group_spacing_strategy_must_be_padding"));
            }
            if (SpacerSizeRule != TEXT("Auto"))
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + TEXT(
                        ":umg_non_group_spacer_size_rule_must_be_auto"));
            }
            if (!FMath::IsNearlyEqual(
                    Layer.SpacerFillCoefficient,
                    1.0,
                    0.000001))
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + TEXT(
                        ":umg_non_group_spacer_fill_coefficient_must_be_one"));
            }
        }
        if (bIsGroup)
        {
            const FString PanelKind = (
                Layer.PanelKind.IsEmpty() || Layer.PanelKind == TEXT("None"))
                ? TEXT("Canvas")
                : Layer.PanelKind;
            if (PanelKind != TEXT("Canvas")
                && PanelKind != TEXT("Horizontal")
                && PanelKind != TEXT("Vertical")
                && PanelKind != TEXT("Grid")
                && PanelKind != TEXT("Overlay"))
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_panel_kind_unsupported:")
                    + PanelKind);
            }
            if (Result.Document.SchemaVersion < 7
                && PanelKind != TEXT("Canvas"))
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_flow_panel_requires_schema_7"));
            }
            if (Result.Document.SchemaVersion < 9
                && PanelKind == TEXT("Grid"))
            {
                Result.BlockReasons.Add(
                    Layer.Id + TEXT(":umg_grid_panel_requires_schema_9"));
            }
            if (Result.Document.SchemaVersion < OverlayPanelSchemaVersion
                && PanelKind == TEXT("Overlay"))
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + TEXT(":umg_overlay_panel_requires_schema_17"));
            }
            if (SpacingStrategy == TEXT("Spacer")
                && PanelKind != TEXT("Horizontal")
                && PanelKind != TEXT("Vertical"))
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + TEXT(":umg_spacer_strategy_requires_linear_panel"));
            }
        }
        switch (Layer.Disposition)
        {
        case ETigerStudioUMGDisposition::Native:
            ++Result.NativeLayerCount;
            break;
        case ETigerStudioUMGDisposition::Material:
        {
            ++Result.MaterialLayerCount;
            const bool bFlipbookMaterial =
                !Layer.Flipbook.AssetId.IsEmpty()
                || !Layer.Flipbook.Schema.IsEmpty()
                || !Layer.Flipbook.Generator.IsEmpty()
                || !Layer.Flipbook.Kind.IsEmpty();
            if (bFlipbookMaterial)
            {
                for (const FString& Reason : ValidateFlipbookLayer(
                         Layer,
                         Result.Document.SchemaVersion,
                         ResourceKinds))
                {
                    Result.BlockReasons.Add(Layer.Id + TEXT(":") + Reason);
                }
                break;
            }
            const bool bRoundedCardMaterial =
                Layer.Material.Schema
                    == TEXT("tigerstudio.umg.ui_material.v2")
                || Layer.Material.Generator
                    == TEXT("tiger_ui_rounded_card_sdf_custom_hlsl_v1")
                || Layer.Material.Kind == TEXT("RoundedCard");
            const int32 RequiredMaterialSchema =
                bRoundedCardMaterial ? 8 : 6;
            if (Result.Document.SchemaVersion < RequiredMaterialSchema)
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + FString::Printf(
                        TEXT(":ui_material_requires_schema_%d"),
                        RequiredMaterialSchema));
                break;
            }
            if (bRoundedCardMaterial
                && RoundedCardRequiresDynamicSizeBinding(
                    Layer,
                    ParentPanelKinds,
                    SyntheticOverlayRootIds)
                && Layer.Material.SizeBinding != TEXT("WidgetGeometry"))
            {
                Result.BlockReasons.Add(
                    Layer.Id
                    + TEXT(
                        ":rounded_card_runtime_resize_requires_dynamic_size_binding"));
            }
            for (const FString& Reason : ValidateMaterialLayer(
                     Layer,
                     Result.Document.SchemaVersion))
            {
                Result.BlockReasons.Add(Layer.Id + TEXT(":") + Reason);
            }
            break;
        }
        case ETigerStudioUMGDisposition::Baked:
            ++Result.BakedLayerCount;
            for (const FString& Reason : ValidateMaterializedBakedLayer(
                     Layer,
                     Result.Document.SchemaVersion,
                     ResourceKinds,
                     ParentPanelKinds,
                     ResourcesById,
                     ResourceFileHashes,
                     ResourceSourcePaths))
            {
                Result.BlockReasons.Add(Layer.Id + TEXT(":") + Reason);
            }
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

    if (!Result.BlockReasons.IsEmpty())
    {
        Result.Message = FString::Printf(
            TEXT("Preflight blocked by unsupported generation layer(s): %s"),
            *FString::Join(Result.BlockReasons, TEXT("; ")));
        return Result;
    }

    Result.bSuccess = true;
    Result.Message =
        TEXT(
            "Tiger UMG document is ready for native/material/materialized-baked generation.");
    return Result;
}
