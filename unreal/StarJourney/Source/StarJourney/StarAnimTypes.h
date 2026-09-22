// Copyright 向星而行. Animation contract shared with the character AnimBP.
#pragma once

#include "CoreMinimal.h"
#include "StarAnimTypes.generated.h"

// Which pose the body should hold right now.
//
// This lives in its own header rather than in StarTypes.h on purpose: StarTypes
// mirrors star.proto (the wire contract with the Go service), while this enum is
// a purely local presentation concern between the pawn and its AnimBP. Keeping
// them apart means an animation iteration never touches the protocol types.
//
// Idle and Run are locomotion; the rest map one-to-one onto the six action
// cycles. Squat is included even though it has no montage: its pose is blended
// from AStarRunnerPawn::GetSquatAlpha().
UENUM(BlueprintType)
enum class EStarAnimState : uint8
{
	Idle,
	Run,
	Squat,
	Jack,
	LaneLeft,
	LaneRight,
	LegLeft,
	LegRight,
};
