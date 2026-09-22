// Copyright 向星而行. In-game HUD (pure C++ Slate; no UMG assets).
#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "StarTypes.h"

// Everything the HUD needs for one frame, gathered by AStarHUD from the pawn and
// the level director. A plain struct keeps the widget free of gameplay
// dependencies: it never queries the world itself.
struct FStarHudState
{
	int32 Starlight = 0;
	int32 CompletedTasks = 0;
	int32 TotalTasks = 0;
	EStarAction CurrentAction = EStarAction::None;
	EStarTracking Tracking = EStarTracking::None;
	bool bWaitingAtStation = false;
	EStarAction RequiredAction = EStarAction::None;
	bool bPaused = false;
	bool bLevelComplete = false;
};

// Read-only status overlay: starlight, task progress, the current action as an
// icon AND text (the design doc requires prompts to never rely on colour alone),
// the action required while stopped at a task station, and the pause notice.
//
// Deliberately pure Slate instead of UMG: WBP assets are binary and cannot be
// authored outside the editor, so keeping the whole HUD as code means it lives in
// version control like the rest of the project.
class STARJOURNEY_API SStarHudWidget : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SStarHudWidget) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);

	// Push one frame of state; called every tick by AStarHUD.
	void Refresh(const FStarHudState& State);

private:
	static FText ActionToText(EStarAction Action);
	static FText TrackingToText(EStarTracking State);
	static FLinearColor ActionToColor(EStarAction Action);

	// The single most useful line: what the player should do right now.
	static FText BuildHint(const FStarHudState& State);

	TSharedPtr<class STextBlock> StarlightText;
	TSharedPtr<class STextBlock> TaskText;
	TSharedPtr<class STextBlock> ActionText;
	TSharedPtr<class STextBlock> TrackingText;
	TSharedPtr<class STextBlock> HintText;
	TSharedPtr<class STextBlock> PauseText;
	TSharedPtr<class SBorder> ActionSwatch;
	TSharedPtr<class SBorder> PausePanel;

	// Read through Slate attributes every frame, so these update without
	// rebuilding the widget tree or calling Invalidate.
	FLinearColor SwatchColor = FLinearColor(0.5f, 0.5f, 0.5f, 1.0f);
	bool bPaused = false;
};
