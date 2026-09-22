// Copyright 向星而行. HUD host: builds the Slate overlay and feeds it state.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "StarHUD.generated.h"

class AStarLevelDirector;
class AStarRunnerPawn;
class SStarHudWidget;

// Owns the in-game HUD widget and refreshes it each frame from the runner pawn
// and the level director. The HUD is read-only: it never mutates gameplay.
UCLASS()
class STARJOURNEY_API AStarHUD : public AHUD
{
	GENERATED_BODY()

public:
	AStarHUD();

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	void RefreshFromWorld();

	// Both are cached (weakly) because the pawn is spawned by the GameMode and
	// the director lives in the level; neither is guaranteed at construction time.
	AStarRunnerPawn* FindRunner();
	AStarLevelDirector* FindDirector();

	TSharedPtr<SStarHudWidget> HudWidget;
	TWeakObjectPtr<AStarRunnerPawn> CachedRunner;
	TWeakObjectPtr<AStarLevelDirector> CachedDirector;
};
