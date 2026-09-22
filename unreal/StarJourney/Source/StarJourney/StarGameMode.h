// Copyright 向星而行. Game mode: binds the runner pawn as the default player.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "StarGameMode.generated.h"

// The gameplay map (L_EchoForest_Play) uses this mode so the player spawns as
// AStarRunnerPawn rather than the default character. It also binds the HUD and
// the pause-handling controller. The runner pawn carries its own fixed rear-view
// camera, so no separate view target is set here.
UCLASS()
class STARJOURNEY_API AStarGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AStarGameMode();
};
