// Copyright 向星而行. Game mode: binds the runner pawn as the default player.
#include "StarGameMode.h"

#include "StarRunnerPawn.h"

AStarGameMode::AStarGameMode()
{
	DefaultPawnClass = AStarRunnerPawn::StaticClass();
}
