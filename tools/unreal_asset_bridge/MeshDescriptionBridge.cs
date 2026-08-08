using System.Buffers.Binary;
using System.Numerics;
using CUE4Parse.Compression;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Assets.Readers;
using CUE4Parse.UE4.Objects.Core.Compression;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Readers;
using CUE4Parse.UE4.Versions;
using K4os.Compression.LZ4;

namespace TigerUnrealAssetBridge.MeshDescription;

public class UMeshDescriptionBaseBulkData : UObject
{
    public FEditorBulkData? EditorBulkData { get; private set; }
    public FGuid Guid { get; private set; }
    public bool GuidIsHash { get; private set; }

    public override void Deserialize(FAssetArchive Ar, long validPos)
    {
        base.Deserialize(Ar, validPos);
        if (Ar.IsFilterEditorOnly || Ar.Position >= validPos) return;
        try
        {
            EditorBulkData = new FEditorBulkData(Ar);
            if (Ar.Position + 16 <= validPos) Guid = Ar.Read<FGuid>();
            if (Ar.Position + 1 <= validPos) GuidIsHash = Ar.ReadBoolean();
        }
        catch
        {
            EditorBulkData = null;
        }
    }
}

public sealed class UStaticMeshDescriptionBulkData : UMeshDescriptionBaseBulkData;
public sealed class USkeletalMeshDescriptionBulkData : UMeshDescriptionBaseBulkData;

public sealed class MeshDescriptionResult
{
    public Vector3[] Positions { get; init; } = [];
    public Vector3[] Normals { get; init; } = [];
    public Vector2[] UVs { get; init; } = [];
    public uint[] TriangleIndices { get; init; } = [];
    public int[] TrianglePolygonGroupIndices { get; init; } = [];
    public string[] MaterialSlotNames { get; init; } = [];
    public int[] BoneIndices { get; init; } = [];
    public float[] BoneWeights { get; init; } = [];
}

public static class MeshDescriptionBulkReader
{
    public static MeshDescriptionResult? TryDecodeFromPackageExports(IEnumerable<UObject> exports, EGame game, Action<string>? diag = null)
    {
        var bulk = SelectPrimaryBulkData(exports.OfType<UMeshDescriptionBaseBulkData>().ToList());
        if (bulk?.EditorBulkData?.Payload is null)
        {
            diag?.Invoke("No MeshDescriptionBulkData payload was found.");
            return null;
        }

        var payload = DecompressPayload(bulk.EditorBulkData.Payload);
        if (payload.Length == 0)
        {
            diag?.Invoke("MeshDescriptionBulkData payload decompressed to zero bytes.");
            return null;
        }
        return MeshDescriptionDecoder.Decode(payload, game, diag);
    }

    private static UMeshDescriptionBaseBulkData? SelectPrimaryBulkData(IReadOnlyList<UMeshDescriptionBaseBulkData> bulks)
    {
        UMeshDescriptionBaseBulkData? best = null;
        var bestRank = int.MaxValue;
        foreach (var bulk in bulks)
        {
            if (bulk.EditorBulkData?.Payload is null) continue;
            if (bulk.EditorBulkData.PayloadSize <= 0) continue;
            var rank = ExtractTrailingNumber(bulk.Name) ?? 1000;
            if (rank >= bestRank) continue;
            bestRank = rank;
            best = bulk;
        }
        return best;
    }

    private static int? ExtractTrailingNumber(string name)
    {
        var index = name.Length;
        while (index > 0 && char.IsDigit(name[index - 1])) index--;
        if (index == name.Length) return null;
        return int.TryParse(name[index..], out var value) ? value : null;
    }

    public static byte[] DecompressPayload(FCompressedBuffer buffer)
    {
        var header = buffer.Header;
        var data = buffer.Data;
        if (header.Method == FCompressedBufferHeader.EMethod.None) return data;

        var blockCount = (int)header.BlockCount;
        var blockSize = 1L << header.BlockSizeExponent;
        var totalRaw = (long)header.TotalRawSize;
        if (blockCount <= 0 || totalRaw <= 0) return [];

        if (header.Method == FCompressedBufferHeader.EMethod.Oodle && OodleHelper.Instance is null)
        {
            OodleHelper.Initialize();
        }

        var blockSizes = new uint[blockCount];
        for (var index = 0; index < blockCount; index++)
            blockSizes[index] = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(index * 4, 4));

        var output = new byte[totalRaw];
        long outputOffset = 0;
        var inputOffset = blockCount * 4;
        for (var index = 0; index < blockCount; index++)
        {
            var rawBlockSize = Math.Min(blockSize, totalRaw - outputOffset);
            var compressedSize = (int)blockSizes[index];
            if (compressedSize >= rawBlockSize)
            {
                Array.Copy(data, inputOffset, output, outputOffset, rawBlockSize);
            }
            else if (header.Method == FCompressedBufferHeader.EMethod.Oodle)
            {
                OodleHelper.Decompress(data, inputOffset, compressedSize, output, (int)outputOffset, (int)rawBlockSize);
            }
            else if (header.Method == FCompressedBufferHeader.EMethod.LZ4)
            {
                var result = LZ4Codec.Decode(data, inputOffset, compressedSize, output, (int)outputOffset, (int)rawBlockSize);
                if (result != rawBlockSize)
                    throw new InvalidOperationException($"LZ4 block {index} decoded {result}/{rawBlockSize} bytes.");
            }
            else
            {
                throw new NotSupportedException($"Unsupported MeshDescription compression method: {header.Method}");
            }
            inputOffset += compressedSize;
            outputOffset += rawBlockSize;
        }
        return output;
    }
}

public static class MeshDescriptionDecoder
{
    private const string ElementVertices = "Vertices";
    private const string ElementVertexInstances = "VertexInstances";
    private const string ElementTriangles = "Triangles";
    private const string ElementPolygonGroups = "PolygonGroups";
    private const string AttrVertexPosition = "Position ";
    private const string AttrVertexSkinWeights = "SkinWeights";
    private const string AttrVertexInstanceVertexIndex = "VertexIndex";
    private const string AttrVertexInstanceNormal = "Normal";
    private const string AttrVertexInstanceUV = "TextureCoordinate";
    private const string AttrTriangleVertexInstanceIndex = "VertexInstanceIndex";
    private const string AttrTrianglePolygonGroupIndex = "PolygonGroupIndex";
    private const string AttrPolygonGroupMaterialSlot = "ImportedMaterialSlotName";

    private enum AttrType : uint
    {
        FVector4f = 0,
        FVector3f = 1,
        FVector2f = 2,
        Float = 3,
        Int32 = 4,
        Bool = 5,
        FName = 6,
        FTransform = 7,
    }

    public static MeshDescriptionResult? Decode(byte[] payload, EGame game, Action<string>? diag = null)
    {
        if (payload.Length == 0) return null;
        var archive = new FByteArchive("MeshDescription", payload, new VersionContainer(game));
        try
        {
            return DecodeNewFormat(archive, diag);
        }
        catch (Exception ex)
        {
            diag?.Invoke($"MeshDescription decode failed at 0x{archive.Position:X}: {ex.GetType().Name}: {ex.Message}");
            return null;
        }
    }

    private static MeshDescriptionResult? DecodeNewFormat(FByteArchive archive, Action<string>? diag)
    {
        var elementMapCount = archive.Read<int>();
        if (elementMapCount < 0 || elementMapCount > 64) return null;

        Vector3[]? vertexPositions = null;
        int[]? vertexInstanceVertexIds = null;
        Vector3[]? vertexInstanceNormals = null;
        Vector2[]? vertexInstanceUvs = null;
        int[][]? triangleVertexInstances = null;
        int[]? trianglePolygonGroupIds = null;
        string[]? polygonGroupSlotNames = null;
        int[][]? vertexSkinWeights = null;

        for (var elementIndex = 0; elementIndex < elementMapCount; elementIndex++)
        {
            var elementName = archive.ReadFString();
            var channelCount = archive.Read<int>();
            if (channelCount < 0 || channelCount > 32) return null;
            for (var channel = 0; channel < channelCount; channel++)
            {
                var container = ReadElementContainer(archive, diag);
                if (container is null) continue;
                switch (elementName)
                {
                    case ElementVertices:
                        if (container.Attributes.TryGetValue(AttrVertexPosition, out var positionEntry))
                            vertexPositions = ReadFVector3fAttribute(positionEntry);
                        if (container.Attributes.TryGetValue(AttrVertexSkinWeights, out var skinEntry))
                            vertexSkinWeights = ReadUnboundedInt32Channel0(skinEntry);
                        break;
                    case ElementVertexInstances:
                        if (container.Attributes.TryGetValue(AttrVertexInstanceVertexIndex, out var vertexIdEntry))
                            vertexInstanceVertexIds = ReadInt32Attribute(vertexIdEntry, 1);
                        if (container.Attributes.TryGetValue(AttrVertexInstanceNormal, out var normalEntry))
                            vertexInstanceNormals = ReadFVector3fAttribute(normalEntry);
                        if (container.Attributes.TryGetValue(AttrVertexInstanceUV, out var uvEntry))
                            vertexInstanceUvs = ReadFVector2fChannel0(uvEntry);
                        break;
                    case ElementTriangles:
                        if (container.Attributes.TryGetValue(AttrTriangleVertexInstanceIndex, out var triangleEntry))
                            triangleVertexInstances = ReadInt32TripletAttribute(triangleEntry);
                        if (container.Attributes.TryGetValue(AttrTrianglePolygonGroupIndex, out var groupEntry))
                            trianglePolygonGroupIds = ReadInt32Attribute(groupEntry, 1);
                        break;
                    case ElementPolygonGroups:
                        if (container.Attributes.TryGetValue(AttrPolygonGroupMaterialSlot, out var slotEntry))
                            polygonGroupSlotNames = ReadFNameAttribute(slotEntry, container.NumElements);
                        break;
                }
            }
        }

        if (vertexPositions is null || vertexInstanceVertexIds is null || triangleVertexInstances is null)
            return null;

        var vertexInstanceCount = vertexInstanceVertexIds.Length;
        var positions = new Vector3[vertexInstanceCount];
        for (var index = 0; index < vertexInstanceCount; index++)
        {
            var vertexId = vertexInstanceVertexIds[index];
            if ((uint)vertexId >= (uint)vertexPositions.Length) return null;
            positions[index] = vertexPositions[vertexId];
        }

        var normals = vertexInstanceNormals?.Length == vertexInstanceCount
            ? vertexInstanceNormals
            : ComputeFaceNormalsAtVI(positions, triangleVertexInstances);
        var uvs = vertexInstanceUvs?.Length == vertexInstanceCount
            ? vertexInstanceUvs
            : new Vector2[vertexInstanceCount];

        var boneIndices = new int[vertexInstanceCount * 4];
        var boneWeights = new float[vertexInstanceCount * 4];
        for (var vi = 0; vi < vertexInstanceCount; vi++)
        {
            var sourceVertex = vertexInstanceVertexIds[vi];
            var packed = vertexSkinWeights is not null && (uint)sourceVertex < (uint)vertexSkinWeights.Length
                ? vertexSkinWeights[sourceVertex]
                : Array.Empty<int>();
            var strongest = packed
                .Select(value => (Bone: (int)((uint)value >> 16), Raw: (int)((uint)value & 0xffffu)))
                .Where(value => value.Raw > 0 && value.Bone < 256)
                .OrderByDescending(value => value.Raw)
                .Take(4)
                .ToArray();
            var sum = strongest.Sum(value => value.Raw);
            if (sum <= 0)
            {
                boneWeights[vi * 4] = 1.0f;
                continue;
            }
            for (var influence = 0; influence < strongest.Length; influence++)
            {
                boneIndices[vi * 4 + influence] = strongest[influence].Bone;
                boneWeights[vi * 4 + influence] = strongest[influence].Raw / (float)sum;
            }
        }

        var indices = new uint[triangleVertexInstances.Length * 3];
        for (var triangle = 0; triangle < triangleVertexInstances.Length; triangle++)
        {
            for (var corner = 0; corner < 3; corner++)
            {
                var vertexInstanceId = triangleVertexInstances[triangle][corner];
                if ((uint)vertexInstanceId >= (uint)vertexInstanceCount) return null;
                indices[triangle * 3 + corner] = (uint)vertexInstanceId;
            }
        }

        return new MeshDescriptionResult
        {
            Positions = positions,
            Normals = normals,
            UVs = uvs,
            TriangleIndices = indices,
            TrianglePolygonGroupIndices = trianglePolygonGroupIds ?? new int[triangleVertexInstances.Length],
            MaterialSlotNames = polygonGroupSlotNames ?? [""],
            BoneIndices = boneIndices,
            BoneWeights = boneWeights,
        };
    }

    private static Vector3[] ComputeFaceNormalsAtVI(Vector3[] positions, int[][] triangles)
    {
        var normals = new Vector3[positions.Length];
        foreach (var triangle in triangles)
        {
            var a = triangle[0];
            var b = triangle[1];
            var c = triangle[2];
            if ((uint)a >= positions.Length || (uint)b >= positions.Length || (uint)c >= positions.Length) continue;
            var face = Vector3.Cross(positions[b] - positions[a], positions[c] - positions[a]);
            normals[a] += face;
            normals[b] += face;
            normals[c] += face;
        }
        for (var index = 0; index < normals.Length; index++)
            normals[index] = normals[index].LengthSquared() > 1e-6f ? Vector3.Normalize(normals[index]) : Vector3.UnitZ;
        return normals;
    }

    private sealed class ElementContainer
    {
        public int NumElements;
        public Dictionary<string, AttributeEntry> Attributes { get; } = new(StringComparer.Ordinal);
    }

    private sealed class AttributeEntry
    {
        public AttrType Type;
        public uint Extent;
        public int NumElements;
        public List<byte[]> ChannelBytes { get; } = [];
        public List<string[]> FNameValues { get; } = [];
        public List<int[][]> UnboundedIntValues { get; } = [];
    }

    private static ElementContainer? ReadElementContainer(FByteArchive archive, Action<string>? diag)
    {
        var numBits = archive.Read<int>();
        if (numBits < 0 || numBits > (1 << 28)) return null;
        archive.Position += ((numBits + 31) / 32) * 4L;
        _ = archive.Read<int>();
        var container = new ElementContainer();
        return ReadAttributesSetBase(archive, container, diag) ? container : null;
    }

    private static bool ReadAttributesSetBase(FByteArchive archive, ElementContainer container, Action<string>? diag)
    {
        container.NumElements = archive.Read<int>();
        if (container.NumElements < 0 || container.NumElements > (1 << 28)) return false;
        var mapCount = archive.Read<int>();
        if (mapCount < 0 || mapCount > 256) return false;

        for (var index = 0; index < mapCount; index++)
        {
            var attributeName = archive.ReadFString();
            var entry = ReadAttributeEntry(archive, diag);
            if (entry is null)
            {
                diag?.Invoke($"Failed to read MeshDescription attribute '{attributeName}'.");
                return false;
            }
            container.Attributes[attributeName] = entry;
        }
        return true;
    }

    private static AttributeEntry? ReadAttributeEntry(FByteArchive archive, Action<string>? diag)
    {
        var typeRaw = archive.Read<uint>();
        if (typeRaw > 7)
        {
            diag?.Invoke($"Invalid MeshDescription attribute type {typeRaw}.");
            return null;
        }
        var type = (AttrType)typeRaw;
        var extent = archive.Read<uint>();
        if (extent == 0) return ReadUnboundedAttribute(archive, type);

        var numElements = archive.Read<int>();
        var channelCount = archive.Read<int>();
        if (numElements < 0 || channelCount < 0 || channelCount > 32) return null;

        var entry = new AttributeEntry { Type = type, Extent = extent, NumElements = numElements };
        for (var channel = 0; channel < channelCount; channel++)
        {
            _ = archive.Read<uint>();
            if (IsBulkSerializable(type))
            {
                var elementSize = archive.Read<int>();
                var count = archive.Read<int>();
                if (elementSize <= 0 || count < 0) return null;
                var byteCount = (long)count * elementSize;
                if (byteCount > int.MaxValue) return null;
                entry.ChannelBytes.Add(archive.ReadBytes((int)byteCount));
            }
            else
            {
                entry.ChannelBytes.Add([]);
                entry.FNameValues.Add(ReadNonBulkChannelValues(archive, type));
            }
        }

        SkipDefaultValue(archive, type);
        archive.Position += 4;
        return entry;
    }

    private static AttributeEntry? ReadUnboundedAttribute(FByteArchive archive, AttrType type)
    {
        var size = SizeOfSimple(type);
        if (size <= 0) return null;
        var numElements = archive.Read<int>();
        var channelCount = archive.Read<int>();
        if (numElements < 0 || channelCount < 0 || channelCount > 32) return null;

        var entry = new AttributeEntry { Type = type, Extent = 0, NumElements = numElements };
        for (var channel = 0; channel < channelCount; channel++)
        {
            var values = type == AttrType.Int32
                ? Enumerable.Range(0, numElements).Select(_ => Array.Empty<int>()).ToArray()
                : null;
            var chunkCount = archive.Read<int>();
            if (chunkCount < 0 || chunkCount > (1 << 24)) return null;

            for (var chunk = 0; chunk < chunkCount; chunk++)
            {
                var dataCount = archive.Read<int>();
                if (dataCount < 0) return null;
                int[]? data = null;
                if (type == AttrType.Int32)
                {
                    data = new int[dataCount];
                    for (var index = 0; index < dataCount; index++) data[index] = archive.Read<int>();
                }
                else
                {
                    archive.Position += (long)dataCount * size;
                }

                var chunkElements = archive.Read<int>();
                if (chunkElements < 0 || chunkElements > 4096) return null;
                var starts = new int[chunkElements];
                var counts = new int[chunkElements];
                for (var index = 0; index < chunkElements; index++) starts[index] = archive.Read<int>();
                for (var index = 0; index < chunkElements; index++) counts[index] = archive.Read<int>();
                archive.Position += (long)chunkElements * 4;

                if (values is null || data is null) continue;
                var globalBase = chunk * 256;
                for (var element = 0; element < chunkElements && globalBase + element < values.Length; element++)
                {
                    var start = starts[element];
                    var count = counts[element];
                    if (start < 0 || count < 0 || start > data.Length - count) return null;
                    if (count == 0) continue;
                    var item = new int[count];
                    Array.Copy(data, start, item, 0, count);
                    values[globalBase + element] = item;
                }
            }

            _ = archive.Read<int>();
            archive.Position += size;
            if (values is not null) entry.UnboundedIntValues.Add(values);
        }

        archive.Position += size;
        archive.Position += 4;
        return entry;
    }

    private static bool IsBulkSerializable(AttrType type) => type is not (AttrType.FName or AttrType.FTransform);

    private static int SizeOfSimple(AttrType type) => type switch
    {
        AttrType.FVector4f => 16,
        AttrType.FVector3f => 12,
        AttrType.FVector2f => 8,
        AttrType.Float => 4,
        AttrType.Int32 => 4,
        AttrType.Bool => 1,
        _ => 0,
    };

    private static string[] ReadNonBulkChannelValues(FByteArchive archive, AttrType type)
    {
        var count = archive.Read<int>();
        if (count < 0) throw new InvalidDataException($"Negative MeshDescription non-bulk count {count}");
        if (type == AttrType.FName)
        {
            var names = new string[count];
            for (var index = 0; index < count; index++) names[index] = archive.ReadFString();
            return names;
        }
        if (type == AttrType.FTransform)
        {
            archive.Position += (long)count * 80;
            return [];
        }
        throw new NotSupportedException($"Unexpected non-bulk MeshDescription attribute type {type}");
    }

    private static void SkipDefaultValue(FByteArchive archive, AttrType type)
    {
        switch (type)
        {
            case AttrType.FVector4f: archive.Position += 16; break;
            case AttrType.FVector3f: archive.Position += 12; break;
            case AttrType.FVector2f: archive.Position += 8; break;
            case AttrType.Float: archive.Position += 4; break;
            case AttrType.Int32: archive.Position += 4; break;
            case AttrType.Bool: archive.Position += 4; break;
            case AttrType.FName: archive.ReadFString(); break;
            case AttrType.FTransform: archive.Position += 80; break;
        }
    }

    private static Vector3[]? ReadFVector3fAttribute(AttributeEntry entry)
    {
        if (entry.Type != AttrType.FVector3f || entry.ChannelBytes.Count == 0) return null;
        var bytes = entry.ChannelBytes[0];
        var count = entry.NumElements;
        if (bytes.Length < count * 12) return null;
        var values = new Vector3[count];
        for (var index = 0; index < count; index++)
        {
            values[index] = new Vector3(
                BitConverter.ToSingle(bytes, index * 12 + 0),
                BitConverter.ToSingle(bytes, index * 12 + 4),
                BitConverter.ToSingle(bytes, index * 12 + 8));
        }
        return values;
    }

    private static Vector2[]? ReadFVector2fChannel0(AttributeEntry entry)
    {
        if (entry.Type != AttrType.FVector2f || entry.ChannelBytes.Count == 0) return null;
        var bytes = entry.ChannelBytes[0];
        var count = entry.NumElements;
        if (bytes.Length < count * 8) return null;
        var values = new Vector2[count];
        for (var index = 0; index < count; index++)
        {
            values[index] = new Vector2(
                BitConverter.ToSingle(bytes, index * 8 + 0),
                BitConverter.ToSingle(bytes, index * 8 + 4));
        }
        return values;
    }

    private static int[]? ReadInt32Attribute(AttributeEntry entry, uint expectedExtent)
    {
        if (entry.Type != AttrType.Int32 || entry.ChannelBytes.Count == 0 || entry.Extent != expectedExtent) return null;
        var bytes = entry.ChannelBytes[0];
        var count = entry.NumElements;
        if (bytes.Length < count * 4) return null;
        var values = new int[count];
        for (var index = 0; index < count; index++)
            values[index] = BitConverter.ToInt32(bytes, index * 4);
        return values;
    }

    private static int[][]? ReadInt32TripletAttribute(AttributeEntry entry)
    {
        if (entry.Type != AttrType.Int32 || entry.ChannelBytes.Count == 0 || entry.Extent != 3) return null;
        var bytes = entry.ChannelBytes[0];
        var count = entry.NumElements;
        if (bytes.Length < count * 12) return null;
        var values = new int[count][];
        for (var index = 0; index < count; index++)
        {
            values[index] =
            [
                BitConverter.ToInt32(bytes, index * 12 + 0),
                BitConverter.ToInt32(bytes, index * 12 + 4),
                BitConverter.ToInt32(bytes, index * 12 + 8),
            ];
        }
        return values;
    }

    private static string[] ReadFNameAttribute(AttributeEntry entry, int expectedSize)
    {
        if (entry.Type != AttrType.FName) return [];
        var values = entry.FNameValues.Count > 0 ? entry.FNameValues[0] : [];
        if (values.Length >= expectedSize) return values;
        var padded = new string[expectedSize];
        Array.Copy(values, padded, values.Length);
        return padded;
    }

    private static int[][]? ReadUnboundedInt32Channel0(AttributeEntry entry)
        => entry.Type == AttrType.Int32 && entry.Extent == 0 && entry.UnboundedIntValues.Count > 0
            ? entry.UnboundedIntValues[0]
            : null;
}
