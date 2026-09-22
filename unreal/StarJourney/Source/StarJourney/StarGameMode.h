// Copyright 向星而行. Game mode: binds the runner pawn as the default player.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "StarGameMode.generated.h"

// The gameplay map (L_EchoForest_Play) uses this mode so the player spawns as
// AStarRunnerPawn rather than the default character. No camera possession is
// forced here; the fixed rear-view camera in the level is set as the player's
// view target by level script.
UCLASS()
class STARJOURNEY_API AStarGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AStarGameMode();
};
