using UnrealBuildTool;

public class TigerStudioUMG : ModuleRules
{
    public TigerStudioUMG(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(
            new[]
            {
                "Core",
                "CoreUObject",
                "Engine",
                "UMG"
            });

        PrivateDependencyModuleNames.AddRange(
            new[]
            {
                "Json",
                "JsonUtilities",
                "Slate",
                "SlateCore"
            });
    }
}
