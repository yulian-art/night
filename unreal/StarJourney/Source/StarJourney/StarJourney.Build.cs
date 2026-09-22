// Copyright 向星而行. Module build rules.
using UnrealBuildTool;

public class StarJourney : ModuleRules
{
	public StarJourney(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			// WebSocket gateway client (Go 127.0.0.1:50052). Engine built-in.
			"WebSockets",
			// Save chain over HTTP+JSON to the same Go service. Engine built-in.
			"Http",
			"Json",
			"JsonUtilities",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Slate",
			"SlateCore",
		});
	}
}
