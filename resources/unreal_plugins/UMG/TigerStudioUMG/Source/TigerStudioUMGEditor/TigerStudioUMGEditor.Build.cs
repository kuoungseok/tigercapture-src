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
                "Json",
                "JsonUtilities",
                "Kismet",
                "KismetCompiler",
                "MovieScene",
                "MovieSceneTracks",
                "Projects",
                "Slate",
                "SlateCore",
                "UMG",
                "UMGEditor",
                "UnrealEd"
            });
    }
}
