using System.Text.Json;
using CUE4Parse.FileProvider;
using CUE4Parse_Conversion;

var command = args.Length > 0 ? args[0].Trim().ToLowerInvariant() : "--info";

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
    Console.WriteLine(JsonSerializer.Serialize(info, new JsonSerializerOptions { WriteIndented = true }));
    return 0;
}

Console.Error.WriteLine($"Unknown command: {command}");
return 2;
