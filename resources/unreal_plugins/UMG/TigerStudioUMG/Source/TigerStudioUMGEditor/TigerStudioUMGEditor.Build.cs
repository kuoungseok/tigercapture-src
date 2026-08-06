using UnrealBuildTool;

public class TigerStudioUMGEditor : ModuleRules
{
    public TigerStudioUMGEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(
            new[]
            {
                "Core",
                "CoreUObject",
                "Engine",
                "TigerStudioUMG"
            });

        PrivateDependencyModuleNames.AddRange(
            new[]
            {
                "AssetRegistry",
                "AssetTools",
                "BlueprintGraph",
                "EditorSubsystem",
                "ImageWrapper",
                "Json",
                "JsonUtilities",
                "Kismet",
                "KismetCompiler",
                "MaterialEditor",
                "MovieScene",
                "MovieSceneTracks",
                "Projects",
                "RenderCore",
                "Slate",
                "SlateCore",
                "UMG",
                "UMGEditor",
                "UnrealEd"
            });

        AddEngineThirdPartyPrivateStaticDependencies(Target, "OpenSSL");
    }
}
