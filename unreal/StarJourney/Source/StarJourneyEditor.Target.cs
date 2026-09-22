// Copyright 向星而行. Editor build target.
using UnrealBuildTool;
using System.Collections.Generic;

public class StarJourneyEditorTarget : TargetRules
{
	public StarJourneyEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("StarJourney");
	}
}
