// Copyright 向星而行. Player controller: Esc toggles the pause.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "StarPlayerController.generated.h"

// Esc pauses and resumes the game. A real engine pause is used (rather than just
// stopping the runner) because the design doc's pause page needs the whole world
// to hold still, and it keeps the Director's progression state intact.
UCLASS()
class STARJOURNEY_API AStarPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	AStarPlayerController();

	virtual void SetupInputComponent() override;

protected:
	// UFUNCTION is required by BindKey's member-pointer overload.
	UFUNCTION()
	void TogglePause();
};
