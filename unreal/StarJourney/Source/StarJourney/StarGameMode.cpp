// Copyright 向星而行. Game mode: binds the runner pawn as the default player.
#include "StarGameMode.h"

#include "StarHUD.h"
#include "StarPlayerController.h"
#include "StarRunnerPawn.h"

AStarGameMode::AStarGameMode()
{
	DefaultPawnClass = AStarRunnerPawn::StaticClass();
	// The HUD and the pause controller ship together with this mode; without them
	// there is no on-screen state and no way to pause.
	HUDClass = AStarHUD::StaticClass();
	PlayerControllerClass = AStarPlayerController::StaticClass();
}
