using System.Globalization;
using System.Text.Json;
using CUE4Parse.FileProvider;
using CUE4Parse.FileProvider.Objects;
using CUE4Parse.UE4.Assets;
using CUE4Parse.UE4.Assets.Exports.Animation;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse.UE4.Objects.Engine.Curves;
using CUE4Parse.UE4.Objects.MovieScene;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion;
using CUE4Parse_Conversion.Animations;
using CUE4Parse_Conversion.Animations.PSA;
using CUE4Parse_Conversion.Meshes;
using CUE4Parse_Conversion.Meshes.PSK;
using TigerUnrealAssetBridge.MeshDescription;

var command = args.Length > 0 ? args[0].Trim().ToLowerInvariant() : "--info";
var jsonOptions = new JsonSerializerOptions { WriteIndented = true };

if (command is "--info" or "info")
{
    var info = new
    {
        ok = true,
        tool = "TigerUnrealAssetBridge",
        runtime = "internal_cue4parse",
        cue4parseAssembly = typeof(DefaultFileProvider).Assembly.GetName().Name,
        conversionAssembly = typeof(ExporterOptions).Assembly.GetName().Name,
        supportedFirstTargets = new[]
        {
            "Blueprint owner skeletal-mesh discovery",
            "Skeletal mesh vertices and indices",
            "Material slot and texture references",
            "AR/PBR .arpbr descriptor export"
        }
    };
    Console.WriteLine(JsonSerializer.Serialize(info, jsonOptions));
    return 0;
}

if (command is "--export-skeletal-mesh" or "export-skeletal-mesh")
{
    try
    {
        var options = ParseOptions(args.Skip(1).ToArray());
        var projectPath = RequiredPath(options, "project");
        var assetPath = RequiredPath(options, "asset");
        var outputPath = RequiredPath(options, "out");
        var maxTriangles = OptionalInt(options, "max-triangles", 240_000);

        var descriptor = ExportSkeletalMeshDescriptor(projectPath, assetPath, maxTriangles);
        var payload = new Dictionary<string, object?>
        {
            ["schema"] = "tigerstudio.ar_pbr.unreal_skeletal_mesh_export.v1",
            ["runtime_format"] = "ar_scene_descriptor",
            ["descriptor"] = descriptor,
        };
        Directory.CreateDirectory(outputPath.DirectoryName ?? ".");
        File.WriteAllText(outputPath.FullName, JsonSerializer.Serialize(payload, jsonOptions));
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            ok = true,
            output = outputPath.FullName,
            mesh = assetPath.FullName,
            triangle_count = descriptor["metadata"] is Dictionary<string, object?> meta ? meta["triangle_count"] : null,
            vertex_count = descriptor["metadata"] is Dictionary<string, object?> meta2 ? meta2["vertex_count"] : null,
        }, jsonOptions));
        return 0;
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine(JsonSerializer.Serialize(new
        {
            ok = false,
            error = ex.GetType().Name,
            message = ex.Message,
        }, jsonOptions));
        return 1;
    }
}

if (command is "--export-animation-clip" or "export-animation-clip")
{
    try
    {
        var options = ParseOptions(args.Skip(1).ToArray());
        var projectPath = RequiredPath(options, "project");
        var assetPath = RequiredPath(options, "asset");
        var outputPath = RequiredPath(options, "out");
        var maxSamples = OptionalInt(options, "max-samples", 90);
        var referenceMeshPath = options.TryGetValue("reference-mesh", out var referenceMeshValue) && !string.IsNullOrWhiteSpace(referenceMeshValue)
            ? new FileInfo(referenceMeshValue)
            : null;

        var clip = ExportAnimationClip(projectPath, assetPath, maxSamples, referenceMeshPath);
        var payload = new Dictionary<string, object?>
        {
            ["schema"] = "tigerstudio.ar_pbr.unreal_animation_clip_export.v1",
            ["animation_clip"] = clip,
        };
        Directory.CreateDirectory(outputPath.DirectoryName ?? ".");
        File.WriteAllText(outputPath.FullName, JsonSerializer.Serialize(payload, jsonOptions));
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            ok = true,
            output = outputPath.FullName,
            animation = assetPath.FullName,
            clip = clip["name"],
            duration_ms = clip["duration_ms"],
        }, jsonOptions));
        return 0;
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine(JsonSerializer.Serialize(new
        {
            ok = false,
            error = ex.GetType().Name,
            message = ex.Message,
        }, jsonOptions));
        return 1;
    }
}

if (command is "--export-animation-clips" or "export-animation-clips")
{
    try
    {
        var options = ParseOptions(args.Skip(1).ToArray());
        var projectPath = RequiredPath(options, "project");
        var batchPath = RequiredPath(options, "batch-json");
        var outputPath = RequiredPath(options, "out");
        var maxSamples = OptionalInt(options, "max-samples", 48);
        var referenceMeshPath = options.TryGetValue("reference-mesh", out var referenceMeshValue) && !string.IsNullOrWhiteSpace(referenceMeshValue)
            ? new FileInfo(referenceMeshValue)
            : null;

        var payload = ExportAnimationClipsBatch(projectPath, batchPath, outputPath, maxSamples, referenceMeshPath);
        Directory.CreateDirectory(outputPath.DirectoryName ?? ".");
        File.WriteAllText(outputPath.FullName, JsonSerializer.Serialize(payload, jsonOptions));
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            ok = true,
            output = outputPath.FullName,
            count = payload.TryGetValue("count", out var count) ? count : null,
            failed_count = payload.TryGetValue("failed_count", out var failedCount) ? failedCount : null,
        }, jsonOptions));
        return 0;
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine(JsonSerializer.Serialize(new
        {
            ok = false,
            error = ex.GetType().Name,
            message = ex.Message,
        }, jsonOptions));
        return 1;
    }
}

if (command is "--inspect-package" or "inspect-package")
{
    try
    {
        var options = ParseOptions(args.Skip(1).ToArray());
        var projectPath = RequiredPath(options, "project");
        var assetPath = RequiredPath(options, "asset");
        var contentRoot = new DirectoryInfo(Path.Combine(projectPath.DirectoryName ?? ".", "Content"));
        using var provider = CreateProvider(projectPath, contentRoot);
        RegisterPackageTree(provider, contentRoot);
        var packagePath = ResolveProviderPath(provider, contentRoot, assetPath);
        var package = provider.LoadPackage(packagePath);
        var exports = package.GetExports().Select(item => new
        {
            name = item.Name,
            export_type = item.ExportType,
            clr_type = item.GetType().FullName,
        }).ToArray();
        var anim = package.GetExports().OfType<UAnimSequence>().FirstOrDefault();
        var animSkeleton = anim is not null ? TryLoadAnimationSkeleton(provider, contentRoot, anim) : null;
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            ok = true,
            package_path = packagePath,
            export_count = exports.Length,
            animation_skeleton_ref = anim is null ? null : DescribeResolvedObject(anim.Skeleton.ResolvedObjectNoCache),
            animation_skeleton_loaded = animSkeleton is not null,
            animation_skeleton_bones = animSkeleton?.BoneCount,
            exports,
        }, jsonOptions));
        return 0;
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine(JsonSerializer.Serialize(new
        {
            ok = false,
            error = ex.GetType().Name,
            message = ex.Message,
        }, jsonOptions));
        return 1;
    }
}

Console.Error.WriteLine($"Unknown command: {command}");
return 2;

static Dictionary<string, object?> ExportSkeletalMeshDescriptor(FileInfo projectPath, FileInfo assetPath, int maxTriangles)
{
    if (!projectPath.Exists)
        throw new FileNotFoundException("Unreal project file was not found.", projectPath.FullName);
    if (!assetPath.Exists)
        throw new FileNotFoundException("Skeletal mesh package was not found.", assetPath.FullName);

    var contentRoot = new DirectoryInfo(Path.Combine(projectPath.DirectoryName ?? ".", "Content"));
    if (!contentRoot.Exists)
        throw new DirectoryNotFoundException($"Content directory not found: {contentRoot.FullName}");
    if (!assetPath.FullName.StartsWith(contentRoot.FullName, StringComparison.OrdinalIgnoreCase))
        throw new InvalidOperationException("Asset must be inside the project's Content directory.");

    using var provider = CreateProvider(projectPath, contentRoot);
    RegisterPackageDirectory(provider, contentRoot, assetPath.DirectoryName ?? contentRoot.FullName);
    var packagePath = ResolveProviderPath(provider, contentRoot, assetPath);
    var package = provider.LoadPackage(packagePath);
    var mesh = package.GetExports().OfType<USkeletalMesh>().FirstOrDefault()
        ?? throw new InvalidOperationException($"No USkeletalMesh export was found in package: {packagePath}");

    List<Dictionary<string, object?>> materials;
    List<Dictionary<string, object?>> geometries;
    List<Dictionary<string, object?>> bones;
    int sourceVertexCount;
    int sourceIndexCount;
    var lodIndex = 0;
    var geometrySource = "cooked_lod_models";

    if (mesh.TryConvert(out var converted) && converted.LODs.Count > 0)
    {
        var lod = converted.LODs[lodIndex];
        if (lod.Verts is null || lod.Verts.Length == 0)
            throw new InvalidOperationException("Converted skeletal mesh LOD has no vertices.");
        if (lod.Indices is null || lod.Indices.Value.Length < 3)
            throw new InvalidOperationException("Converted skeletal mesh LOD has no triangle indices.");
        materials = BuildMaterials(mesh, lod);
        geometries = BuildCookedGeometries(mesh, lod, materials, maxTriangles);
        bones = BuildBones(converted.RefSkeleton);
        sourceVertexCount = lod.Verts.Length;
        sourceIndexCount = lod.Indices.Value.Length;
    }
    else
    {
        var warnings = new List<string>();
        var decoded = MeshDescriptionBulkReader.TryDecodeFromPackageExports(
            package.GetExports(),
            provider.Versions.Game,
            message => warnings.Add(message));
        if (decoded is null)
            throw new InvalidOperationException("CUE4Parse could not convert this skeletal mesh and no MeshDescriptionBulkData fallback was decoded.");
        geometrySource = "mesh_description_bulk_data";
        materials = BuildMaterials(mesh, null);
        geometries = BuildMeshDescriptionGeometries(mesh, decoded, materials, maxTriangles);
        bones = BuildBonesFromReferenceSkeleton(mesh.ReferenceSkeleton);
        sourceVertexCount = decoded.Positions.Length;
        sourceIndexCount = decoded.TriangleIndices.Length;
        if (warnings.Count > 0)
        {
            foreach (var geometry in geometries)
                geometry["mesh_description_warnings"] = warnings.ToArray();
        }
    }
    if (geometries.Count == 0)
        throw new InvalidOperationException("Converted skeletal mesh did not produce any AR/PBR geometry sections.");

    var bounds = BoundsFromGeometries(geometries);
    var modelId = $"model_{SanitizeId(mesh.Name)}";
    var triangleCount = geometries.Sum(g => Convert.ToInt32(g["triangle_count"], CultureInfo.InvariantCulture));
    var vertexCount = geometries.Sum(g => Convert.ToInt32(g["stored_vertex_count"], CultureInfo.InvariantCulture));
    return new Dictionary<string, object?>
    {
        ["schema"] = "tigerstudio.ar_pbr.unreal_skeletal_mesh_export.v1",
        ["id"] = $"unreal_skeletal_{SanitizeId(mesh.Name)}",
        ["type"] = "ar_pbr_asset",
        ["source_format"] = "unreal_skeletal_mesh",
        ["runtime_format"] = "ar_scene_descriptor",
        ["import_state"] = "ready",
        ["backend"] = "internal_cue4parse",
        ["mesh_count"] = geometries.Count,
        ["material_count"] = materials.Count,
        ["texture_count"] = 0,
        ["animation_count"] = 0,
        ["animation_clips"] = Array.Empty<object>(),
        ["skeletal_mesh_count"] = 1,
        ["skin_count"] = 1,
        ["skeletons"] = new[]
        {
            new Dictionary<string, object?>
            {
                ["id"] = "skeleton_0",
                ["name"] = $"{mesh.Name} Reference Skeleton",
                ["bone_count"] = bones.Count,
            },
        },
        ["bones"] = bones,
        ["units"] = new Dictionary<string, object?>
        {
            ["scale_to_meters"] = 0.01,
            ["source"] = "unreal_centimeters",
        },
        ["axes"] = new Dictionary<string, object?>
        {
            ["up"] = "Y",
            ["forward"] = "+X",
            ["source"] = "unreal_z_up_converted_to_tiger_y_up",
        },
        ["bounds"] = bounds,
        ["materials"] = materials,
        ["geometries"] = geometries,
        ["models"] = new[]
        {
            new Dictionary<string, object?>
            {
                ["id"] = modelId,
                ["name"] = mesh.Name,
                ["type"] = "SkeletalMesh",
                ["translation"] = new[] { 0.0, 0.0, 0.0 },
                ["rotation"] = new[] { 0.0, 0.0, 0.0 },
                ["scale"] = new[] { 1.0, 1.0, 1.0 },
            },
        },
        ["connections"] = geometries.SelectMany(g => new[]
        {
            new Dictionary<string, object?> { ["child"] = g["id"], ["parent"] = modelId, ["type"] = "Geometry" },
            new Dictionary<string, object?> { ["child"] = g["material_id"], ["parent"] = modelId, ["type"] = "Material" },
        }).ToArray(),
        ["warnings"] = Array.Empty<object>(),
        ["metadata"] = new Dictionary<string, object?>
        {
            ["project_path"] = projectPath.FullName,
            ["source_asset_path"] = assetPath.FullName,
            ["package_path"] = packagePath,
            ["export_name"] = mesh.Name,
            ["geometry_source"] = geometrySource,
            ["lod_index"] = lodIndex,
            ["source_vertex_count"] = sourceVertexCount,
            ["source_index_count"] = sourceIndexCount,
            ["vertex_count"] = vertexCount,
            ["triangle_count"] = triangleCount,
            ["section_count"] = geometries.Count,
            ["max_triangles"] = maxTriangles,
        },
    };
}

static Dictionary<string, object?> ExportAnimationClip(FileInfo projectPath, FileInfo assetPath, int maxSamples, FileInfo? referenceMeshPath = null)
{
    if (!projectPath.Exists)
        throw new FileNotFoundException("Unreal project file was not found.", projectPath.FullName);
    if (!assetPath.Exists)
        throw new FileNotFoundException("Animation package was not found.", assetPath.FullName);
    if (referenceMeshPath is not null && !referenceMeshPath.Exists)
        throw new FileNotFoundException("Reference skeletal mesh package was not found.", referenceMeshPath.FullName);

    var contentRoot = new DirectoryInfo(Path.Combine(projectPath.DirectoryName ?? ".", "Content"));
    if (!contentRoot.Exists)
        throw new DirectoryNotFoundException($"Content directory not found: {contentRoot.FullName}");
    if (!assetPath.FullName.StartsWith(contentRoot.FullName, StringComparison.OrdinalIgnoreCase))
        throw new InvalidOperationException("Animation asset must be inside the project's Content directory.");

    using var provider = CreateProvider(projectPath, contentRoot);
    RegisterPackageTree(provider, contentRoot);
    return ExportAnimationClipWithProvider(provider, contentRoot, assetPath, maxSamples, referenceMeshPath);
}

static Dictionary<string, object?> ExportAnimationClipWithProvider(
    DefaultFileProvider provider,
    DirectoryInfo contentRoot,
    FileInfo assetPath,
    int maxSamples,
    FileInfo? referenceMeshPath = null)
{
    var packagePath = ResolveProviderPath(provider, contentRoot, assetPath);
    var package = provider.LoadPackage(packagePath);
    var anim = package.GetExports().OfType<UAnimSequence>().FirstOrDefault()
        ?? throw new InvalidOperationException($"No UAnimSequence export was found in package: {packagePath}");
    var skeleton = TryLoadAnimationSkeleton(provider, contentRoot, anim) ?? TryLoadReferenceMeshSkeleton(provider, contentRoot, referenceMeshPath);

    var conversionErrors = new List<string>();
    if (skeleton is null)
        conversionErrors.Add($"skeleton_unresolved:{DescribeResolvedObject(anim.Skeleton.ResolvedObjectNoCache)}");

    var sequencerClip = TryExportSequencerAnimationClip(
        package,
        anim,
        assetPath,
        maxSamples,
        provider,
        contentRoot,
        referenceMeshPath);
    if (sequencerClip is not null)
    {
        if (conversionErrors.Count > 0)
            sequencerClip["conversion_notes"] = conversionErrors.ToArray();
        return sequencerClip;
    }

    CAnimSet? animSet = null;
    var sourceMode = "";

    try
    {
        animSet = anim.ConvertAnims();
        sourceMode = "cue4parse_animation_asset_convert_anims";
    }
    catch (Exception ex)
    {
        conversionErrors.Add($"animation_asset:{ex.GetType().Name}:{ex.Message}");
    }

    if (animSet is null && skeleton is not null)
    {
        try
        {
            animSet = skeleton.ConvertAnims(anim);
            sourceMode = "cue4parse_reference_skeleton_convert_anims";
        }
        catch (Exception ex)
        {
            conversionErrors.Add($"reference_skeleton:{ex.GetType().Name}:{ex.Message}");
        }
    }

    if (animSet is null)
    {
        try
        {
            var rawClip = ExportRawAnimationClip(anim, assetPath, maxSamples);
            if (conversionErrors.Count > 0)
                rawClip["conversion_errors"] = conversionErrors.ToArray();
            return rawClip;
        }
        catch (Exception rawEx)
        {
            conversionErrors.Add($"raw_animation_data:{rawEx.GetType().Name}:{rawEx.Message}");
            throw new InvalidOperationException(
                $"Animation conversion failed for {assetPath.FullName}: {string.Join("; ", conversionErrors)}",
                rawEx);
        }
    }

    var sequence = animSet.Sequences.FirstOrDefault()
        ?? throw new InvalidOperationException($"Animation conversion produced no sequence: {packagePath}");
    return ExportConvertedAnimationClip(anim, sequence, assetPath, maxSamples, sourceMode);
}

static Dictionary<string, object?> ExportConvertedAnimationClip(
    UAnimSequence anim,
    CUE4Parse_Conversion.Animations.PSA.CAnimSequence sequence,
    FileInfo assetPath,
    int maxSamples,
    string sourceMode)
{
    var sampleFrames = SampleFrames(Math.Max(1, sequence.NumFrames), Math.Max(2, maxSamples)).ToArray();
    var modelCurves = new Dictionary<string, object?>();
    for (var boneIndex = 0; boneIndex < sequence.Tracks.Count; boneIndex++)
    {
        var track = sequence.Tracks[boneIndex];
        if (!track.HasKeys()) continue;
        var tx = new List<double[]>();
        var ty = new List<double[]>();
        var tz = new List<double[]>();
        var qx = new List<double[]>();
        var qy = new List<double[]>();
        var qz = new List<double[]>();
        var qw = new List<double[]>();
        var sx = new List<double[]>();
        var sy = new List<double[]>();
        var sz = new List<double[]>();
        foreach (var frame in sampleFrames)
        {
            var q = FQuat.Identity;
            var p = FVector.ZeroVector;
            var s = new FVector(1.0f, 1.0f, 1.0f);
            track.GetBoneTransform(frame, sequence.NumFrames, ref q, ref p, ref s);
            var timeMs = FrameToMilliseconds(frame, sequence);
            var tp = ToTigerPosition(p);
            var tq = ToTigerQuaternion(q);
            tx.Add([timeMs, tp[0]]);
            ty.Add([timeMs, tp[1]]);
            tz.Add([timeMs, tp[2]]);
            qx.Add([timeMs, tq[0]]);
            qy.Add([timeMs, tq[1]]);
            qz.Add([timeMs, tq[2]]);
            qw.Add([timeMs, tq[3]]);
            sx.Add([timeMs, Round(s.X)]);
            sy.Add([timeMs, Round(s.Y)]);
            sz.Add([timeMs, Round(s.Z)]);
        }
        modelCurves[$"bone_{boneIndex}"] = new Dictionary<string, object?>
        {
            ["translation"] = new Dictionary<string, object?> { ["x"] = tx, ["y"] = ty, ["z"] = tz },
            ["rotation_quat"] = new Dictionary<string, object?> { ["x"] = qx, ["y"] = qy, ["z"] = qz, ["w"] = qw },
            ["scale"] = new Dictionary<string, object?> { ["x"] = sx, ["y"] = sy, ["z"] = sz },
        };
    }

    return new Dictionary<string, object?>
    {
        ["id"] = SanitizeId(assetPath.Name),
        ["name"] = anim.Name,
        ["source_asset_path"] = assetPath.FullName,
        ["source_mode"] = string.IsNullOrWhiteSpace(sourceMode) ? "cue4parse_convert_anims" : sourceMode,
        ["duration_ms"] = Round(Math.Max(0.001, sequence.AnimEndTime) * 1000.0),
        ["frame_count"] = sequence.NumFrames,
        ["frames_per_second"] = Round(sequence.FramesPerSecond),
        ["sampled_frame_count"] = sampleFrames.Length,
        ["rotation_space"] = "tiger_basis_quat_v1",
        ["model_curves"] = modelCurves,
    };
}

static Dictionary<string, object?>? TryExportSequencerAnimationClip(
    IPackage package,
    UAnimSequence anim,
    FileInfo assetPath,
    int maxSamples,
    DefaultFileProvider provider,
    DirectoryInfo contentRoot,
    FileInfo? referenceMeshPath = null)
{
    var section = package.GetExports().FirstOrDefault(item =>
        item.ExportType == "MovieSceneControlRigParameterSection");
    if (section is null)
        return null;

    var parameters = section.GetOrDefault<FStructFallback[]>(
        "TransformParameterNamesAndCurves",
        Array.Empty<FStructFallback>());
    if (parameters.Length == 0)
        return null;

    var frameCount = Math.Max(anim.NumFrames, 1);
    var durationSeconds = Math.Max(0.0f, anim.SequenceLength);
    var frameRate = durationSeconds > 0.0f && frameCount > 1 ? (frameCount - 1) / durationSeconds : 30.0f;

    var lastChannelFrame = -1;
    foreach (var parameter in parameters)
    {
        lastChannelFrame = Math.Max(lastChannelFrame, FindLastSequencerFrame(parameter, "Translation"));
        lastChannelFrame = Math.Max(lastChannelFrame, FindLastSequencerFrame(parameter, "Rotation"));
        lastChannelFrame = Math.Max(lastChannelFrame, FindLastSequencerFrame(parameter, "Scale"));
    }
    frameCount = Math.Max(frameCount, lastChannelFrame + 1);
    frameCount = Math.Max(frameCount, 1);
    if (durationSeconds <= 0.0f && frameRate > 0.0f && frameCount > 1)
        durationSeconds = (frameCount - 1) / frameRate;
    frameRate = durationSeconds > 0.0f && frameCount > 1 ? (frameCount - 1) / durationSeconds : 30.0f;

    var sampleFrames = SampleFrames(frameCount, Math.Max(2, maxSamples)).ToArray();
    var boneIndexByName = TryLoadReferenceMeshBoneIndexMap(provider, contentRoot, referenceMeshPath);
    var modelCurves = new Dictionary<string, object?>();
    var boneNames = new List<string>();
    var unnamedIndex = 0;

    foreach (var parameter in parameters)
    {
        parameter.TryGetAllValues<FMovieSceneChannel<float>>(out var translation, "Translation");
        parameter.TryGetAllValues<FMovieSceneChannel<float>>(out var rotation, "Rotation");
        parameter.TryGetAllValues<FMovieSceneChannel<float>>(out var scale, "Scale");

        var controlName = parameter.GetOrDefault<FName>("ParameterName").Text;
        if (string.IsNullOrWhiteSpace(controlName) || controlName == "None")
            continue;
        var boneName = ControlRigTargetName(controlName);
        var curveKey = boneIndexByName.TryGetValue(boneName, out var boneIndex)
            ? $"bone_{boneIndex}"
            : $"bone_sequencer_{unnamedIndex++}";
        if (modelCurves.ContainsKey(curveKey))
            continue;

        var tx = new List<double[]>();
        var ty = new List<double[]>();
        var tz = new List<double[]>();
        var qx = new List<double[]>();
        var qy = new List<double[]>();
        var qz = new List<double[]>();
        var qw = new List<double[]>();
        var sx = new List<double[]>();
        var sy = new List<double[]>();
        var sz = new List<double[]>();

        foreach (var frame in sampleFrames)
        {
            var timeMs = FrameToMillisecondsFromDuration(frame, frameCount, durationSeconds * 1000.0);
            var pos = new FVector(
                EvaluateSequencerChannel(translation, 0, frame, 0.0f),
                EvaluateSequencerChannel(translation, 1, frame, 0.0f),
                EvaluateSequencerChannel(translation, 2, frame, 0.0f));
            var rotX = EvaluateSequencerChannel(rotation, 0, frame, 0.0f);
            var rotY = EvaluateSequencerChannel(rotation, 1, frame, 0.0f);
            var rotZ = EvaluateSequencerChannel(rotation, 2, frame, 0.0f);
            var scl = new FVector(
                EvaluateSequencerChannel(scale, 0, frame, 1.0f),
                EvaluateSequencerChannel(scale, 1, frame, 1.0f),
                EvaluateSequencerChannel(scale, 2, frame, 1.0f));

            // Unreal's FQuat::MakeFromEuler(X,Y,Z) maps to FRotator(Pitch=Y,Yaw=Z,Roll=X).
            var quat = new FRotator(rotY, rotZ, rotX).Quaternion();
            var tp = ToTigerPosition(pos);
            var tq = ToTigerQuaternion(quat);
            tx.Add([timeMs, tp[0]]);
            ty.Add([timeMs, tp[1]]);
            tz.Add([timeMs, tp[2]]);
            qx.Add([timeMs, tq[0]]);
            qy.Add([timeMs, tq[1]]);
            qz.Add([timeMs, tq[2]]);
            qw.Add([timeMs, tq[3]]);
            sx.Add([timeMs, Round(scl.X)]);
            sy.Add([timeMs, Round(scl.Y)]);
            sz.Add([timeMs, Round(scl.Z)]);
        }

        boneNames.Add(boneName);
        modelCurves[curveKey] = new Dictionary<string, object?>
        {
            ["bone_name"] = boneName,
            ["translation"] = new Dictionary<string, object?> { ["x"] = tx, ["y"] = ty, ["z"] = tz },
            ["rotation_quat"] = new Dictionary<string, object?> { ["x"] = qx, ["y"] = qy, ["z"] = qz, ["w"] = qw },
            ["scale"] = new Dictionary<string, object?> { ["x"] = sx, ["y"] = sy, ["z"] = sz },
        };
    }

    if (modelCurves.Count == 0)
        return null;

    return new Dictionary<string, object?>
    {
        ["id"] = SanitizeId(assetPath.Name),
        ["name"] = anim.Name,
        ["source_asset_path"] = assetPath.FullName,
        ["source_mode"] = "ue5_control_rig_sequencer_curves",
        ["duration_ms"] = Round(Math.Max(0.001, durationSeconds) * 1000.0),
        ["frame_count"] = frameCount,
        ["frames_per_second"] = Round(frameRate),
        ["sampled_frame_count"] = sampleFrames.Length,
        ["rotation_space"] = "tiger_basis_quat_v1",
        ["bone_names"] = boneNames.ToArray(),
        ["model_curves"] = modelCurves,
    };
}

static Dictionary<string, int> TryLoadReferenceMeshBoneIndexMap(
    DefaultFileProvider provider,
    DirectoryInfo contentRoot,
    FileInfo? referenceMeshPath)
{
    var outMap = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    if (referenceMeshPath is null || !referenceMeshPath.Exists)
        return outMap;
    try
    {
        var packagePath = ResolveProviderPath(provider, contentRoot, referenceMeshPath);
        var package = provider.LoadPackage(packagePath);
        var mesh = package.GetExports().OfType<USkeletalMesh>().FirstOrDefault();
        var bones = mesh?.ReferenceSkeleton?.FinalRefBoneInfo;
        if (bones is null)
            return outMap;
        for (var idx = 0; idx < bones.Length; idx++)
        {
            var name = bones[idx].Name.Text;
            if (!string.IsNullOrWhiteSpace(name) && !outMap.ContainsKey(name))
                outMap[name] = idx;
        }
    }
    catch
    {
        return outMap;
    }
    return outMap;
}

static int FindLastSequencerFrame(FStructFallback parameter, string channelName)
{
    if (!parameter.TryGetAllValues<FMovieSceneChannel<float>>(out var channels, channelName))
        return -1;
    var last = -1;
    foreach (var channel in channels)
    {
        if (channel.Times is { Length: > 0 })
            last = Math.Max(last, channel.Times[^1].Value);
    }
    return last;
}

static float EvaluateSequencerChannel(
    FMovieSceneChannel<float>[] channels,
    int axis,
    float frame,
    float fallback)
{
    if ((uint)axis >= (uint)channels.Length)
        return fallback;
    var channel = channels[axis];
    var keyTimes = channel.Times;
    var values = channel.Values;
    if (keyTimes is null || values is null || keyTimes.Length == 0 || values.Length == 0)
        return channel.bHasDefaultValue && channel.DefaultValue is float defaultValue ? defaultValue : fallback;

    var count = Math.Min(keyTimes.Length, values.Length);
    if (frame <= keyTimes[0].Value)
        return values[0].Value;
    if (frame >= keyTimes[count - 1].Value)
        return values[count - 1].Value;

    var lo = 0;
    var hi = count - 1;
    while (hi - lo > 1)
    {
        var mid = (lo + hi) >> 1;
        if (keyTimes[mid].Value <= frame) lo = mid; else hi = mid;
    }
    if (Math.Abs(keyTimes[lo].Value - frame) < 0.0001f)
        return values[lo].Value;

    var span = keyTimes[hi].Value - keyTimes[lo].Value;
    if (span <= 0.0f)
        return values[lo].Value;
    var alpha = (frame - keyTimes[lo].Value) / span;
    return values[lo].InterpMode switch
    {
        ERichCurveInterpMode.RCIM_Constant => values[lo].Value,
        ERichCurveInterpMode.RCIM_Cubic => CubicHermite(
            values[lo].Value,
            values[lo].Tangent.LeaveTangent * span,
            values[hi].Value,
            values[hi].Tangent.ArriveTangent * span,
            alpha),
        _ => float.Lerp(values[lo].Value, values[hi].Value, alpha),
    };
}

static float CubicHermite(float p0, float m0, float p1, float m1, float t)
{
    var t2 = t * t;
    var t3 = t2 * t;
    return (2.0f * t3 - 3.0f * t2 + 1.0f) * p0 +
           (t3 - 2.0f * t2 + t) * m0 +
           (-2.0f * t3 + 3.0f * t2) * p1 +
           (t3 - t2) * m1;
}

static string ControlRigTargetName(string controlName)
{
    var suffix = controlName.IndexOf("_CONTROL", StringComparison.Ordinal);
    return suffix >= 0 ? controlName[..suffix] : controlName;
}

static Dictionary<string, object?> ExportAnimationClipsBatch(
    FileInfo projectPath,
    FileInfo batchPath,
    FileInfo outputPath,
    int maxSamples,
    FileInfo? referenceMeshPath = null)
{
    if (!projectPath.Exists)
        throw new FileNotFoundException("Unreal project file was not found.", projectPath.FullName);
    if (!batchPath.Exists)
        throw new FileNotFoundException("Animation batch manifest was not found.", batchPath.FullName);

    var contentRoot = new DirectoryInfo(Path.Combine(projectPath.DirectoryName ?? ".", "Content"));
    if (!contentRoot.Exists)
        throw new DirectoryNotFoundException($"Content directory not found: {contentRoot.FullName}");
    if (referenceMeshPath is not null && !referenceMeshPath.Exists)
        throw new FileNotFoundException("Reference skeletal mesh package was not found.", referenceMeshPath.FullName);

    var items = ReadAnimationBatchItems(batchPath, maxSamples);
    using var provider = CreateProvider(projectPath, contentRoot);
    RegisterPackageTree(provider, contentRoot);

    var results = new List<Dictionary<string, object?>>();
    var okCount = 0;
    foreach (var item in items)
    {
        var assetPath = item.AssetPath;
        var itemSamples = Math.Max(2, item.MaxSamples > 0 ? item.MaxSamples : maxSamples);
        var targetPath = item.OutputPath;
        var result = new Dictionary<string, object?>
        {
            ["source_file"] = assetPath.FullName,
            ["out"] = targetPath.FullName,
            ["ok"] = false,
        };

        try
        {
            if (!assetPath.Exists)
                throw new FileNotFoundException("Animation package was not found.", assetPath.FullName);
            if (!assetPath.FullName.StartsWith(contentRoot.FullName, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Animation asset must be inside the project's Content directory.");

            var clip = ExportAnimationClipWithProvider(provider, contentRoot, assetPath, itemSamples, referenceMeshPath);
            var clipPayload = new Dictionary<string, object?>
            {
                ["schema"] = "tigerstudio.ar_pbr.unreal_animation_clip_export.v1",
                ["exporter"] = "internal_cue4parse_batch",
                ["animation_clip"] = clip,
            };
            Directory.CreateDirectory(targetPath.DirectoryName ?? ".");
            File.WriteAllText(targetPath.FullName, JsonSerializer.Serialize(clipPayload, new JsonSerializerOptions { WriteIndented = true }));
            okCount++;
            result["ok"] = true;
            result["clip"] = clip;
        }
        catch (Exception ex)
        {
            result["error"] = ex.GetType().Name;
            result["message"] = ex.Message;
        }

        results.Add(result);
    }

    return new Dictionary<string, object?>
    {
        ["schema"] = "tigerstudio.ar_pbr.unreal_animation_batch_export.v1",
        ["exporter"] = "internal_cue4parse_batch",
        ["ok"] = okCount == items.Count,
        ["count"] = items.Count,
        ["exported_count"] = okCount,
        ["failed_count"] = Math.Max(0, items.Count - okCount),
        ["manifest"] = outputPath.FullName,
        ["results"] = results,
    };
}

static List<(FileInfo AssetPath, FileInfo OutputPath, int MaxSamples)> ReadAnimationBatchItems(FileInfo batchPath, int defaultMaxSamples)
{
    using var doc = JsonDocument.Parse(File.ReadAllText(batchPath.FullName));
    var root = doc.RootElement;
    var array = root.ValueKind == JsonValueKind.Object && root.TryGetProperty("items", out var itemsElement)
        ? itemsElement
        : root;
    if (array.ValueKind != JsonValueKind.Array)
        throw new InvalidOperationException("Animation batch manifest must be an array or an object with an items array.");

    var items = new List<(FileInfo AssetPath, FileInfo OutputPath, int MaxSamples)>();
    foreach (var element in array.EnumerateArray())
    {
        var asset = JsonString(element, "asset") ?? JsonString(element, "source_file") ?? JsonString(element, "animation_path");
        var output = JsonString(element, "out") ?? JsonString(element, "output") ?? JsonString(element, "cache_path");
        if (string.IsNullOrWhiteSpace(asset) || string.IsNullOrWhiteSpace(output))
            continue;
        var samples = JsonInt(element, "max_samples", defaultMaxSamples);
        items.Add((new FileInfo(asset), new FileInfo(output), samples));
    }
    if (items.Count == 0)
        throw new InvalidOperationException("Animation batch manifest did not contain any usable items.");
    return items;
}

static string? JsonString(JsonElement element, string property)
{
    if (!element.TryGetProperty(property, out var value))
        return null;
    return value.ValueKind == JsonValueKind.String ? value.GetString() : value.ToString();
}

static int JsonInt(JsonElement element, string property, int fallback)
{
    if (!element.TryGetProperty(property, out var value))
        return fallback;
    if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var parsed))
        return Math.Max(1, parsed);
    return int.TryParse(value.ToString(), NumberStyles.Integer, CultureInfo.InvariantCulture, out parsed)
        ? Math.Max(1, parsed)
        : fallback;
}

static Dictionary<string, object?> ExportRawAnimationClip(UAnimSequence anim, FileInfo assetPath, int maxSamples)
{
    var rawTracks = anim.RawAnimationData ?? Array.Empty<FRawAnimSequenceTrack>();
    if (rawTracks.Length == 0)
        throw new InvalidOperationException($"Animation skeleton could not be loaded and raw animation tracks are not available: {assetPath.FullName}");

    var frameCount = Math.Max(1, anim.NumFrames);
    if (frameCount <= 1)
    {
        frameCount = rawTracks.Max(track => Math.Max(Math.Max(track.PosKeys?.Length ?? 0, track.RotKeys?.Length ?? 0), track.ScaleKeys?.Length ?? 0));
        frameCount = Math.Max(1, frameCount);
    }
    var durationSeconds = anim.SequenceLength > 0.0f ? anim.SequenceLength : Math.Max(1.0, frameCount - 1.0) / 30.0;
    var sampleFrames = SampleFrames(frameCount, Math.Max(2, maxSamples)).ToArray();
    var trackMap = anim.GetTrackMap();
    var modelCurves = new Dictionary<string, object?>();

    for (var trackIndex = 0; trackIndex < rawTracks.Length; trackIndex++)
    {
        var raw = rawTracks[trackIndex];
        var track = new CAnimTrack
        {
            KeyPos = raw.PosKeys ?? Array.Empty<FVector>(),
            KeyQuat = raw.RotKeys ?? Array.Empty<FQuat>(),
            KeyScale = raw.ScaleKeys ?? Array.Empty<FVector>(),
            KeyTime = raw.KeyTimes ?? Array.Empty<float>(),
        };
        if (!track.HasKeys()) continue;

        var boneIndex = trackIndex < trackMap.Length ? trackMap[trackIndex].BoneTreeIndex : trackIndex;
        if (boneIndex < 0) boneIndex = trackIndex;
        var tx = new List<double[]>();
        var ty = new List<double[]>();
        var tz = new List<double[]>();
        var qx = new List<double[]>();
        var qy = new List<double[]>();
        var qz = new List<double[]>();
        var qw = new List<double[]>();
        var sx = new List<double[]>();
        var sy = new List<double[]>();
        var sz = new List<double[]>();
        foreach (var frame in sampleFrames)
        {
            var q = FQuat.Identity;
            var p = FVector.ZeroVector;
            var s = new FVector(1.0f, 1.0f, 1.0f);
            track.GetBoneTransform(frame, frameCount, ref q, ref p, ref s);
            var timeMs = FrameToMillisecondsFromDuration(frame, frameCount, durationSeconds * 1000.0);
            var tp = ToTigerPosition(p);
            var tq = ToTigerQuaternion(q);
            tx.Add([timeMs, tp[0]]);
            ty.Add([timeMs, tp[1]]);
            tz.Add([timeMs, tp[2]]);
            qx.Add([timeMs, tq[0]]);
            qy.Add([timeMs, tq[1]]);
            qz.Add([timeMs, tq[2]]);
            qw.Add([timeMs, tq[3]]);
            sx.Add([timeMs, Round(s.X)]);
            sy.Add([timeMs, Round(s.Y)]);
            sz.Add([timeMs, Round(s.Z)]);
        }
        modelCurves[$"bone_{boneIndex}"] = new Dictionary<string, object?>
        {
            ["translation"] = new Dictionary<string, object?> { ["x"] = tx, ["y"] = ty, ["z"] = tz },
            ["rotation_quat"] = new Dictionary<string, object?> { ["x"] = qx, ["y"] = qy, ["z"] = qz, ["w"] = qw },
            ["scale"] = new Dictionary<string, object?> { ["x"] = sx, ["y"] = sy, ["z"] = sz },
        };
    }

    return new Dictionary<string, object?>
    {
        ["id"] = SanitizeId(assetPath.Name),
        ["name"] = anim.Name,
        ["source_asset_path"] = assetPath.FullName,
        ["source_mode"] = "raw_animation_data",
        ["duration_ms"] = Round(durationSeconds * 1000.0),
        ["frame_count"] = frameCount,
        ["frames_per_second"] = Round(frameCount / Math.Max(0.001, durationSeconds)),
        ["sampled_frame_count"] = sampleFrames.Length,
        ["rotation_space"] = "tiger_basis_quat_v1",
        ["model_curves"] = modelCurves,
    };
}

static USkeleton? TryLoadAnimationSkeleton(DefaultFileProvider provider, DirectoryInfo contentRoot, UAnimSequence anim)
{
    try
    {
        if (anim.Skeleton.TryLoad<USkeleton>(out var skeleton))
            return skeleton;
    }
    catch
    {
        // Some UE5 editor assets omit or defer the direct Skeleton reference.
    }

    try
    {
        return anim.Skeleton.Load<USkeleton>();
    }
    catch
    {
    }

    return TryLoadSkeletonFromResolvedObject(provider, contentRoot, anim.Skeleton.ResolvedObjectNoCache);
}

static USkeleton? TryLoadReferenceMeshSkeleton(DefaultFileProvider provider, DirectoryInfo contentRoot, FileInfo? referenceMeshPath)
{
    if (referenceMeshPath is null)
        return null;
    if (!referenceMeshPath.FullName.StartsWith(contentRoot.FullName, StringComparison.OrdinalIgnoreCase))
        throw new InvalidOperationException("Reference skeletal mesh must be inside the project's Content directory.");

    var packagePath = ResolveProviderPath(provider, contentRoot, referenceMeshPath);
    var package = provider.LoadPackage(packagePath);
    var mesh = package.GetExports().OfType<USkeletalMesh>().FirstOrDefault();
    if (mesh is null)
        return null;

    try
    {
        if (mesh.Skeleton.TryLoad<USkeleton>(out var skeleton))
            return skeleton;
    }
    catch
    {
        // The mesh reference skeleton is still used by mesh export; animation conversion needs USkeleton.
    }

    try
    {
        return mesh.Skeleton.Load<USkeleton>();
    }
    catch
    {
    }

    return TryLoadSkeletonFromResolvedObject(provider, contentRoot, mesh.Skeleton.ResolvedObjectNoCache);
}

static USkeleton? TryLoadSkeletonFromResolvedObject(
    DefaultFileProvider provider,
    DirectoryInfo contentRoot,
    CUE4Parse.UE4.Assets.ResolvedObject? resolved)
{
    foreach (var packagePath in PackagePathCandidatesFromResolvedObject(provider, resolved))
    {
        try
        {
            var package = provider.LoadPackage(packagePath);
            var skeleton = package.GetExports().OfType<USkeleton>().FirstOrDefault();
            if (skeleton is not null)
                return skeleton;
        }
        catch
        {
            // Try the next path spelling. Provider keys can be bare, Game/, or /Game/.
        }
    }
    return null;
}

static IEnumerable<string> PackagePathCandidatesFromResolvedObject(
    DefaultFileProvider provider,
    CUE4Parse.UE4.Assets.ResolvedObject? resolved)
{
    if (resolved is null)
        yield break;

    var candidates = new List<string>();
    var top = resolved;
    while (top.Outer is not null)
        top = top.Outer;
    AddPackagePathCandidate(candidates, top.Name.Text);
    AddPackagePathCandidate(candidates, resolved.GetPathName());

    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    foreach (var candidate in candidates)
    {
        foreach (var resolvedCandidate in ResolveProviderPackagePathCandidates(provider, candidate))
        {
            if (seen.Add(resolvedCandidate))
                yield return resolvedCandidate;
        }
    }
}

static void AddPackagePathCandidate(List<string> candidates, string? value)
{
    var text = (value ?? "").Trim();
    if (string.IsNullOrWhiteSpace(text) || text.Equals("None", StringComparison.OrdinalIgnoreCase))
        return;
    var quoteStart = text.IndexOf('\'');
    var quoteEnd = text.LastIndexOf('\'');
    if (quoteStart >= 0 && quoteEnd > quoteStart)
        text = text[(quoteStart + 1)..quoteEnd];
    var colon = text.IndexOf(':');
    if (colon > 0)
        text = text[..colon];
    var dot = text.LastIndexOf('.');
    if (dot > 0 && text[(dot + 1)..].IndexOf('/') < 0)
        text = text[..dot];
    if (!string.IsNullOrWhiteSpace(text))
        candidates.Add(text);
}

static string DescribeResolvedObject(CUE4Parse.UE4.Assets.ResolvedObject? resolved)
{
    if (resolved is null)
        return "null";
    try
    {
        var top = resolved;
        while (top.Outer is not null)
            top = top.Outer;
        return $"top={top.Name.Text}, path={resolved.GetPathName()}";
    }
    catch (Exception ex)
    {
        return $"{resolved.Name.Text}:{ex.GetType().Name}:{ex.Message}";
    }
}

static IEnumerable<string> ResolveProviderPackagePathCandidates(DefaultFileProvider provider, string unrealPackagePath)
{
    var normalized = unrealPackagePath.Replace('\\', '/').Trim();
    if (normalized.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase) ||
        normalized.EndsWith(".umap", StringComparison.OrdinalIgnoreCase))
    {
        normalized = normalized[..normalized.LastIndexOf('.')];
    }

    var rel = normalized;
    if (rel.StartsWith("/Game/", StringComparison.OrdinalIgnoreCase))
        rel = rel[6..];
    else if (rel.StartsWith("Game/", StringComparison.OrdinalIgnoreCase))
        rel = rel[5..];
    else
        rel = rel.TrimStart('/');

    foreach (var prefix in new[] { "/Game/", "Game/", "" })
    {
        var packagePath = prefix + rel;
        if (provider.Files.ContainsKey(packagePath + ".uasset") || provider.Files.ContainsKey(packagePath + ".umap"))
            yield return packagePath;
    }

    foreach (var ext in new[] { ".uasset", ".umap" })
    {
        var suffix = "/" + rel + ext;
        foreach (var key in provider.Files.Keys)
        {
            if (!key.EndsWith(ext, StringComparison.OrdinalIgnoreCase))
                continue;
            if (key.EndsWith(suffix, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(key, rel + ext, StringComparison.OrdinalIgnoreCase))
            {
                yield return key[..^ext.Length];
                break;
            }
        }
    }
}

static DefaultFileProvider CreateProvider(FileInfo projectPath, DirectoryInfo contentRoot)
{
    ObjectTypeRegistry.RegisterEngine(typeof(UMeshDescriptionBaseBulkData).Assembly);
    var game = MapEngineAssociation(ReadEngineAssociation(projectPath));
    var provider = new DefaultFileProvider(
        directory: contentRoot.FullName,
        searchOption: SearchOption.TopDirectoryOnly,
        versions: new VersionContainer(game),
        pathComparer: StringComparer.OrdinalIgnoreCase);
    provider.Initialize();
    return provider;
}

static string ReadEngineAssociation(FileInfo projectPath)
{
    try
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(projectPath.FullName));
        if (doc.RootElement.TryGetProperty("EngineAssociation", out var value))
            return value.GetString() ?? "";
    }
    catch
    {
        return "";
    }
    return "";
}

static EGame MapEngineAssociation(string value)
{
    var text = (value ?? "").Trim();
    var parts = text.Split('.', StringSplitOptions.RemoveEmptyEntries);
    if (parts.Length >= 2 &&
        int.TryParse(parts[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out var major) &&
        int.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var minor))
    {
        if (major == 5 && minor == 5) return EGame.GAME_UE5_5;
        if (major == 5 && minor >= 6) return EGame.GAME_UE5_6;
    }
    return EGame.GAME_UE5_5;
}

static void RegisterPackageDirectory(DefaultFileProvider provider, DirectoryInfo contentRoot, string directoryPath)
{
    var directory = new DirectoryInfo(directoryPath);
    if (!directory.Exists) return;
    var files = new Dictionary<string, GameFile>(StringComparer.OrdinalIgnoreCase);
    foreach (var path in Directory.EnumerateFiles(directory.FullName, "*.*", SearchOption.TopDirectoryOnly))
    {
        var ext = Path.GetExtension(path);
        if (!IsPackageSidecarExtension(ext)) continue;
        var gameFile = new OsGameFile(contentRoot, new FileInfo(path), "Content/", provider.Versions);
        files[gameFile.Path] = gameFile;
    }
    if (files.Count > 0)
        provider.Files.AddFiles(files, 1);
}

static void RegisterPackageTree(DefaultFileProvider provider, DirectoryInfo contentRoot)
{
    if (!contentRoot.Exists) return;
    var files = new Dictionary<string, GameFile>(StringComparer.OrdinalIgnoreCase);
    foreach (var path in Directory.EnumerateFiles(contentRoot.FullName, "*.*", SearchOption.AllDirectories))
    {
        var ext = Path.GetExtension(path);
        if (!IsPackageSidecarExtension(ext)) continue;
        var gameFile = new OsGameFile(contentRoot, new FileInfo(path), "Content/", provider.Versions);
        files[gameFile.Path] = gameFile;
    }
    if (files.Count > 0)
        provider.Files.AddFiles(files, 1);
}

static string ResolveProviderPath(DefaultFileProvider provider, DirectoryInfo contentRoot, FileInfo assetPath)
{
    var rel = Path.GetRelativePath(contentRoot.FullName, assetPath.FullName).Replace('\\', '/');
    var dot = rel.LastIndexOf('.');
    var relNoExt = dot > 0 ? rel[..dot] : rel;
    foreach (var prefix in new[] { "/Game/", "Game/", "" })
    {
        var withExt = prefix + relNoExt + ".uasset";
        if (provider.Files.ContainsKey(withExt))
            return prefix + relNoExt;
    }
    var suffix = "/" + relNoExt + ".uasset";
    foreach (var key in provider.Files.Keys)
    {
        if (!key.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)) continue;
        if (key.EndsWith(suffix, StringComparison.OrdinalIgnoreCase) ||
            string.Equals(key, relNoExt + ".uasset", StringComparison.OrdinalIgnoreCase))
            return key[..^".uasset".Length];
    }
    return "/Game/" + relNoExt;
}

static bool IsPackageSidecarExtension(string extension)
    => extension.Equals(".uasset", StringComparison.OrdinalIgnoreCase) ||
       extension.Equals(".umap", StringComparison.OrdinalIgnoreCase) ||
       extension.Equals(".uexp", StringComparison.OrdinalIgnoreCase) ||
       extension.Equals(".ubulk", StringComparison.OrdinalIgnoreCase) ||
       extension.Equals(".uptnl", StringComparison.OrdinalIgnoreCase);

static List<Dictionary<string, object?>> BuildMaterials(USkeletalMesh mesh, CSkelMeshLod? lod)
{
    var skeletalMaterials = mesh.SkeletalMaterials ?? [];
    var materialCount = Math.Max(skeletalMaterials.Length, 1);
    var materialIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var materials = new List<Dictionary<string, object?>>();
    for (var idx = 0; idx < materialCount; idx++)
    {
        var slotName = idx < skeletalMaterials.Length
            ? skeletalMaterials[idx].MaterialSlotName.Text
            : $"material_{idx}";
        var id = $"mat_{idx}_{SanitizeId(slotName)}";
        if (!materialIds.Add(id))
            id = $"mat_{idx}";
        materials.Add(new Dictionary<string, object?>
        {
            ["id"] = id,
            ["name"] = string.IsNullOrWhiteSpace(slotName) ? $"Material {idx}" : slotName,
            ["base_color"] = MaterialBaseColor(idx),
            ["roughness"] = idx % 3 == 0 ? 0.42 : 0.58,
            ["metallic"] = 0.0,
            ["reflectance"] = 0.54,
            ["pbr_available"] = true,
            ["source_material_index"] = idx,
        });
    }

    foreach (var section in lod?.Sections?.Value ?? Array.Empty<CMeshSection>())
    {
        if (section.MaterialIndex < 0 || section.MaterialIndex >= materials.Count) continue;
        if (!string.IsNullOrWhiteSpace(section.MaterialName))
            materials[section.MaterialIndex]["name"] = section.MaterialName;
    }
    return materials;
}

static List<Dictionary<string, object?>> BuildMeshDescriptionGeometries(
    USkeletalMesh mesh,
    MeshDescriptionResult decoded,
    List<Dictionary<string, object?>> materials,
    int maxTriangles)
{
    var groups = new Dictionary<int, List<int>>();
    for (var tri = 0; tri < decoded.TriangleIndices.Length / 3; tri++)
    {
        var group = tri < decoded.TrianglePolygonGroupIndices.Length ? decoded.TrianglePolygonGroupIndices[tri] : 0;
        if (!groups.TryGetValue(group, out var list))
        {
            list = [];
            groups[group] = list;
        }
        list.Add(tri);
    }

    var slotToMaterialIndex = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    var skeletalMaterials = mesh.SkeletalMaterials ?? [];
    for (var idx = 0; idx < skeletalMaterials.Length; idx++)
    {
        var slot = skeletalMaterials[idx].MaterialSlotName.Text;
        if (!string.IsNullOrWhiteSpace(slot) && !slotToMaterialIndex.ContainsKey(slot))
            slotToMaterialIndex[slot] = idx;
    }

    var geometries = new List<Dictionary<string, object?>>();
    var remainingTriangles = Math.Max(1, maxTriangles);
    foreach (var (groupIndex, sourceTriangles) in groups.OrderBy(item => item.Key))
    {
        if (remainingTriangles <= 0) break;
        var useTriangleCount = Math.Min(sourceTriangles.Count, remainingTriangles);
        var stride = Math.Max(1, (int)Math.Ceiling(sourceTriangles.Count / (double)useTriangleCount));
        var vertexMap = new Dictionary<uint, int>();
        var outVertices = new List<double[]>();
        var outNormals = new List<double[]>();
        var outUvs = new List<double[]>();
        var outWeights = new List<Dictionary<string, object?>>();
        var outTriangles = new List<int[]>();

        for (var index = 0; index < sourceTriangles.Count && outTriangles.Count < useTriangleCount; index += stride)
        {
            var sourceTri = sourceTriangles[index];
            var baseIndex = sourceTri * 3;
            if (baseIndex + 2 >= decoded.TriangleIndices.Length) continue;
            var a = RemapDecodedVertex(decoded.TriangleIndices[baseIndex], decoded, vertexMap, outVertices, outNormals, outUvs, outWeights);
            var b = RemapDecodedVertex(decoded.TriangleIndices[baseIndex + 1], decoded, vertexMap, outVertices, outNormals, outUvs, outWeights);
            var c = RemapDecodedVertex(decoded.TriangleIndices[baseIndex + 2], decoded, vertexMap, outVertices, outNormals, outUvs, outWeights);
            if (a < 0 || b < 0 || c < 0) continue;
            outTriangles.Add([a, b, c]);
        }

        if (outTriangles.Count == 0) continue;
        var slotName = groupIndex >= 0 && groupIndex < decoded.MaterialSlotNames.Length
            ? decoded.MaterialSlotNames[groupIndex]
            : "";
        var materialIndex = slotToMaterialIndex.TryGetValue(slotName, out var mappedMaterial)
            ? mappedMaterial
            : Math.Clamp(groupIndex, 0, Math.Max(0, materials.Count - 1));
        var materialId = materials.Count > 0 ? Convert.ToString(materials[materialIndex]["id"], CultureInfo.InvariantCulture) ?? "mat_0" : "mat_0";
        geometries.Add(new Dictionary<string, object?>
        {
            ["id"] = $"geom_meshdesc_group_{groupIndex}",
            ["name"] = $"{mesh.Name} MeshDescription Group {groupIndex}",
            ["kind"] = "mesh",
            ["material_id"] = materialId,
            ["source_material_index"] = materialIndex,
            ["source_material_slot"] = slotName,
            ["source_triangle_count"] = sourceTriangles.Count,
            ["vertex_count"] = decoded.Positions.Length,
            ["stored_vertex_count"] = outVertices.Count,
            ["triangle_count"] = outTriangles.Count,
            ["decimated"] = outTriangles.Count < sourceTriangles.Count,
            ["vertices"] = outVertices,
            ["normals"] = outNormals,
            ["uvs"] = outUvs,
            ["triangles"] = outTriangles,
            ["skin_weights"] = outWeights,
            ["bounds"] = BoundsFromVertices(outVertices),
        });
        remainingTriangles -= outTriangles.Count;
    }
    return geometries;
}

static List<Dictionary<string, object?>> BuildCookedGeometries(
    USkeletalMesh mesh,
    CSkelMeshLod lod,
    List<Dictionary<string, object?>> materials,
    int maxTriangles)
{
    var vertices = lod.Verts ?? Array.Empty<CSkelMeshVertex>();
    var indices = lod.Indices?.Value ?? Array.Empty<uint>();
    var sections = lod.Sections?.Value;
    if (sections is null || sections.Length == 0)
    {
        sections =
        [
            new CMeshSection(0, 0, indices.Length / 3, "Default", null)
        ];
    }

    var geometries = new List<Dictionary<string, object?>>();
    var remainingTriangles = Math.Max(1, maxTriangles);
    for (var sectionIndex = 0; sectionIndex < sections.Length && remainingTriangles > 0; sectionIndex++)
    {
        var section = sections[sectionIndex];
        var first = Math.Max(0, section.FirstIndex);
        var availableIndexCount = Math.Max(0, Math.Min(indices.Length - first, section.NumFaces * 3));
        var sourceTriangleCount = availableIndexCount / 3;
        if (sourceTriangleCount <= 0) continue;
        var useTriangleCount = Math.Min(sourceTriangleCount, remainingTriangles);
        var stride = Math.Max(1, (int)Math.Ceiling(sourceTriangleCount / (double)useTriangleCount));
        var vertexMap = new Dictionary<uint, int>();
        var outVertices = new List<double[]>();
        var outNormals = new List<double[]>();
        var outUvs = new List<double[]>();
        var outWeights = new List<Dictionary<string, object?>>();
        var outTriangles = new List<int[]>();

        for (var tri = 0; tri < sourceTriangleCount && outTriangles.Count < useTriangleCount; tri += stride)
        {
            var baseIndex = first + tri * 3;
            if (baseIndex + 2 >= indices.Length) break;
            var a = RemapVertex(indices[baseIndex], vertices, vertexMap, outVertices, outNormals, outUvs, outWeights);
            var b = RemapVertex(indices[baseIndex + 1], vertices, vertexMap, outVertices, outNormals, outUvs, outWeights);
            var c = RemapVertex(indices[baseIndex + 2], vertices, vertexMap, outVertices, outNormals, outUvs, outWeights);
            if (a < 0 || b < 0 || c < 0) continue;
            outTriangles.Add([a, b, c]);
        }

        if (outTriangles.Count == 0) continue;
        var materialIndex = Math.Clamp(section.MaterialIndex, 0, Math.Max(0, materials.Count - 1));
        var materialId = materials.Count > 0 ? Convert.ToString(materials[materialIndex]["id"], CultureInfo.InvariantCulture) ?? "mat_0" : "mat_0";
        var geometry = new Dictionary<string, object?>
        {
            ["id"] = $"geom_lod0_section_{sectionIndex}",
            ["name"] = $"{mesh.Name} LOD0 Section {sectionIndex}",
            ["kind"] = "mesh",
            ["material_id"] = materialId,
            ["source_material_index"] = section.MaterialIndex,
            ["source_first_index"] = section.FirstIndex,
            ["source_triangle_count"] = sourceTriangleCount,
            ["vertex_count"] = vertices.Length,
            ["stored_vertex_count"] = outVertices.Count,
            ["triangle_count"] = outTriangles.Count,
            ["decimated"] = outTriangles.Count < sourceTriangleCount,
            ["vertices"] = outVertices,
            ["normals"] = outNormals,
            ["uvs"] = outUvs,
            ["triangles"] = outTriangles,
            ["skin_weights"] = outWeights,
            ["bounds"] = BoundsFromVertices(outVertices),
        };
        geometries.Add(geometry);
        remainingTriangles -= outTriangles.Count;
    }
    return geometries;
}

static int RemapVertex(
    uint sourceIndex,
    CSkelMeshVertex[] vertices,
    Dictionary<uint, int> vertexMap,
    List<double[]> outVertices,
    List<double[]> outNormals,
    List<double[]> outUvs,
    List<Dictionary<string, object?>> outWeights)
{
    if (sourceIndex >= vertices.Length) return -1;
    if (vertexMap.TryGetValue(sourceIndex, out var mapped))
        return mapped;
    var vertex = vertices[sourceIndex];
    mapped = outVertices.Count;
    vertexMap[sourceIndex] = mapped;
    outVertices.Add(ToTigerPosition(vertex.Position));
    outNormals.Add(ToTigerNormal(vertex.Normal));
    outUvs.Add(new[] { Round(vertex.UV.U), Round(vertex.UV.V) });
    outWeights.Add(new Dictionary<string, object?>
    {
        ["joints"] = vertex.Influences.Take(4).Select(item => (int)item.Bone).ToArray(),
        ["weights"] = vertex.Influences.Take(4).Select(item => Round(item.Weight)).ToArray(),
    });
    return mapped;
}

static int RemapDecodedVertex(
    uint sourceIndex,
    MeshDescriptionResult decoded,
    Dictionary<uint, int> vertexMap,
    List<double[]> outVertices,
    List<double[]> outNormals,
    List<double[]> outUvs,
    List<Dictionary<string, object?>> outWeights)
{
    if (sourceIndex >= decoded.Positions.Length) return -1;
    if (vertexMap.TryGetValue(sourceIndex, out var mapped))
        return mapped;
    mapped = outVertices.Count;
    vertexMap[sourceIndex] = mapped;
    outVertices.Add(ToTigerPosition3(decoded.Positions[sourceIndex]));
    outNormals.Add(sourceIndex < decoded.Normals.Length ? ToTigerNormal3(decoded.Normals[sourceIndex]) : [0.0, 1.0, 0.0]);
    outUvs.Add(sourceIndex < decoded.UVs.Length ? [Round(decoded.UVs[sourceIndex].X), Round(decoded.UVs[sourceIndex].Y)] : [0.0, 0.0]);
    var baseInfluence = (int)sourceIndex * 4;
    outWeights.Add(new Dictionary<string, object?>
    {
        ["joints"] = Enumerable.Range(0, 4)
            .Select(offset => baseInfluence + offset < decoded.BoneIndices.Length ? decoded.BoneIndices[baseInfluence + offset] : 0)
            .ToArray(),
        ["weights"] = Enumerable.Range(0, 4)
            .Select(offset => baseInfluence + offset < decoded.BoneWeights.Length ? Round(decoded.BoneWeights[baseInfluence + offset]) : (offset == 0 ? 1.0 : 0.0))
            .ToArray(),
    });
    return mapped;
}

static List<Dictionary<string, object?>> BuildBones(List<CSkelMeshBone> bones)
{
    var outBones = new List<Dictionary<string, object?>>();
    for (var idx = 0; idx < bones.Count; idx++)
    {
        var bone = bones[idx];
        outBones.Add(new Dictionary<string, object?>
        {
            ["id"] = $"bone_{idx}",
            ["index"] = idx,
            ["name"] = bone.Name.Text,
            ["parent_index"] = bone.ParentIndex,
            ["parent_id"] = bone.ParentIndex >= 0 ? $"bone_{bone.ParentIndex}" : "",
            ["translation"] = ToTigerPosition(bone.Position),
            ["rotation_quat"] = ToTigerQuaternion(bone.Orientation),
            ["scale"] = new[] { 1.0, 1.0, 1.0 },
        });
    }
    return outBones;
}

static List<Dictionary<string, object?>> BuildBonesFromReferenceSkeleton(FReferenceSkeleton skeleton)
{
    var outBones = new List<Dictionary<string, object?>>();
    var infos = skeleton.FinalRefBoneInfo ?? [];
    var poses = skeleton.FinalRefBonePose ?? [];
    for (var idx = 0; idx < infos.Length; idx++)
    {
        var translation = idx < poses.Length ? ToTigerPosition(poses[idx].Translation) : [0.0, 0.0, 0.0];
        var rotation = idx < poses.Length
            ? ToTigerQuaternion(poses[idx].Rotation)
            : new[] { 0.0, 0.0, 0.0, 1.0 };
        outBones.Add(new Dictionary<string, object?>
        {
            ["id"] = $"bone_{idx}",
            ["index"] = idx,
            ["name"] = infos[idx].Name.Text,
            ["parent_index"] = infos[idx].ParentIndex,
            ["parent_id"] = infos[idx].ParentIndex >= 0 ? $"bone_{infos[idx].ParentIndex}" : "",
            ["translation"] = translation,
            ["rotation_quat"] = rotation,
            ["scale"] = new[] { 1.0, 1.0, 1.0 },
        });
    }
    return outBones;
}

static double[] ToTigerPosition(FVector value)
    => [Round(value.X * 0.01), Round(value.Z * 0.01), Round(-value.Y * 0.01)];

static double[] ToTigerPosition3(System.Numerics.Vector3 value)
    => [Round(value.X * 0.01), Round(value.Z * 0.01), Round(-value.Y * 0.01)];

static double[] ToTigerQuaternion(FQuat value)
    => NormalizeQuaternion(value.X, value.Z, -value.Y, value.W);

static double[] NormalizeQuaternion(double x, double y, double z, double w)
{
    var length = Math.Sqrt(x * x + y * y + z * z + w * w);
    if (length <= 1.0e-9) return [0.0, 0.0, 0.0, 1.0];
    return [Round(x / length), Round(y / length), Round(z / length), Round(w / length)];
}

static double[] ToTigerNormal(FVector4 value)
{
    var x = value.X;
    var y = value.Z;
    var z = -value.Y;
    var length = Math.Sqrt(x * x + y * y + z * z);
    if (length <= 1.0e-9) return [0.0, 1.0, 0.0];
    return [Round(x / length), Round(y / length), Round(z / length)];
}

static double[] ToTigerNormal3(System.Numerics.Vector3 value)
{
    var x = value.X;
    var y = value.Z;
    var z = -value.Y;
    var length = Math.Sqrt(x * x + y * y + z * z);
    if (length <= 1.0e-9) return [0.0, 1.0, 0.0];
    return [Round(x / length), Round(y / length), Round(z / length)];
}

static Dictionary<string, object?> BoundsFromGeometries(IEnumerable<Dictionary<string, object?>> geometries)
{
    var vertices = geometries
        .SelectMany(g => g["vertices"] as IEnumerable<double[]> ?? Array.Empty<double[]>())
        .ToList();
    return BoundsFromVertices(vertices);
}

static Dictionary<string, object?> BoundsFromVertices(IReadOnlyList<double[]> vertices)
{
    if (vertices.Count == 0)
    {
        return new Dictionary<string, object?>
        {
            ["center"] = new[] { 0.0, 0.0, 0.0 },
            ["size"] = new[] { 1.0, 1.0, 1.0 },
        };
    }
    var min = new[] { double.PositiveInfinity, double.PositiveInfinity, double.PositiveInfinity };
    var max = new[] { double.NegativeInfinity, double.NegativeInfinity, double.NegativeInfinity };
    foreach (var vertex in vertices)
    {
        for (var i = 0; i < 3; i++)
        {
            min[i] = Math.Min(min[i], vertex[i]);
            max[i] = Math.Max(max[i], vertex[i]);
        }
    }
    return new Dictionary<string, object?>
    {
        ["center"] = new[] { Round((min[0] + max[0]) * 0.5), Round((min[1] + max[1]) * 0.5), Round((min[2] + max[2]) * 0.5) },
        ["size"] = new[] { Round(Math.Max(max[0] - min[0], 1.0e-6)), Round(Math.Max(max[1] - min[1], 1.0e-6)), Round(Math.Max(max[2] - min[2], 1.0e-6)) },
    };
}

static double[] MaterialBaseColor(int index)
{
    double[][] palette =
    [
        [0.64, 0.66, 0.63, 1.0],
        [0.20, 0.21, 0.20, 1.0],
        [0.92, 0.42, 0.14, 1.0],
        [0.08, 0.09, 0.10, 1.0],
    ];
    return palette[Math.Abs(index) % palette.Length];
}

static string SanitizeId(string? text)
{
    var raw = string.IsNullOrWhiteSpace(text) ? "item" : text.Trim();
    var chars = raw.Select(ch => char.IsLetterOrDigit(ch) ? char.ToLowerInvariant(ch) : '_').ToArray();
    var compact = new string(chars);
    while (compact.Contains("__", StringComparison.Ordinal))
        compact = compact.Replace("__", "_", StringComparison.Ordinal);
    return compact.Trim('_').Length > 0 ? compact.Trim('_') : "item";
}

static double Round(double value)
    => Math.Round(value, 6, MidpointRounding.AwayFromZero);

static IEnumerable<float> SampleFrames(int frameCount, int maxSamples)
{
    if (frameCount <= 1)
    {
        yield return 0.0f;
        yield break;
    }
    var sampleCount = Math.Min(frameCount, Math.Max(2, maxSamples));
    for (var idx = 0; idx < sampleCount; idx++)
    {
        var value = (frameCount - 1) * (idx / (double)(sampleCount - 1));
        yield return (float)value;
    }
}

static double FrameToMilliseconds(float frame, CUE4Parse_Conversion.Animations.PSA.CAnimSequence sequence)
{
    if (sequence.NumFrames <= 1)
        return 0.0;
    var durationMs = Math.Max(0.001, sequence.AnimEndTime) * 1000.0;
    return Round(durationMs * frame / Math.Max(1.0, sequence.NumFrames - 1.0));
}

static double FrameToMillisecondsFromDuration(float frame, int frameCount, double durationMs)
{
    if (frameCount <= 1)
        return 0.0;
    return Round(Math.Max(0.001, durationMs) * frame / Math.Max(1.0, frameCount - 1.0));
}

static Dictionary<string, string> ParseOptions(string[] values)
{
    var options = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    for (var i = 0; i < values.Length; i++)
    {
        var token = values[i];
        if (!token.StartsWith("--", StringComparison.Ordinal)) continue;
        var key = token[2..];
        var next = i + 1 < values.Length ? values[i + 1] : "";
        if (string.IsNullOrWhiteSpace(next) || next.StartsWith("--", StringComparison.Ordinal))
        {
            options[key] = "true";
            continue;
        }
        options[key] = next;
        i++;
    }
    return options;
}

static FileInfo RequiredPath(Dictionary<string, string> options, string key)
{
    if (!options.TryGetValue(key, out var value) || string.IsNullOrWhiteSpace(value))
        throw new ArgumentException($"Missing required --{key} argument.");
    return new FileInfo(value);
}

static int OptionalInt(Dictionary<string, string> options, string key, int fallback)
{
    if (options.TryGetValue(key, out var value) &&
        int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed))
        return Math.Max(1, parsed);
    return fallback;
}
