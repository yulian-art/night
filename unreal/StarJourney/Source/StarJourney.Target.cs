// Copyright 向星而行. Game build target.
using UnrealBuildTool;
using System.Collections.Generic;

public class StarJourneyTarget : TargetRules
{
	public StarJourneyTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("StarJourney");
	}
}
