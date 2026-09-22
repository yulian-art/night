// Copyright 向星而行. Three-lane runner driven by action events.
#include "StarRunnerPawn.h"

#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "StarInputComponent.h"

AStarRunnerPawn::AStarRunnerPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	Capsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Capsule"));
	Capsule->InitCapsuleSize(40.0f, 90.0f);
	Capsule->SetCollisionProfileName(TEXT("Pawn"));
	RootComponent = Capsule;

	VisualRoot = CreateDefaultSubobject<USceneComponent>(TEXT("VisualRoot"));
	VisualRoot->SetupAttachment(Capsule);

	Input = CreateDefaultSubobject<UStarInputComponent>(TEXT("Input"));
}

void AStarRunnerPawn::BeginPlay()
{
	Super::BeginPlay();
	// Spawn Y is the center lane; lanes are spaced around it.
	CenterLineY = GetActorLocation().Y;
	LaneStartY = LaneTargetY = CenterLineY;
}

void AStarRunnerPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	if (Input)
	{
		Input->BindKeyboard(PlayerInputComponent);
	}
}

void AStarRunnerPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UpdateForward(DeltaSeconds);
	UpdateLane(DeltaSeconds);
	UpdateJump(DeltaSeconds);
	UpdateSquat(DeltaSeconds);
	ApplyVisualOffset();
}

// ---------------------------------------------------------------------------
// External control
// ---------------------------------------------------------------------------

void AStarRunnerPawn::SetRunning(bool bNewRunning)
{
	bRunning = bNewRunning;
}

// ---------------------------------------------------------------------------
// Action handling. Mirrors the four documented UE input checks:
//   1. generation is owned by the input component, not checked here;
//   2. gameplay may forbid an action (CanStartAction);
//   3. Begin requires Ready and no other active action;
//   4. Complete/Cancel must match the active action (Ready not required).
// ---------------------------------------------------------------------------

bool AStarRunnerPawn::CanStartAction(EStarAction Action) const
{
	if (Action == EStarAction::None)
	{
		return false;
	}
	// Outermost lane cannot jump further outward.
	if (Action == EStarAction::JumpLeft && Lane == EStarLane::Left)
	{
		return false;
	}
	if (Action == EStarAction::JumpRight && Lane == EStarLane::Right)
	{
		return false;
	}
	return true;
}

bool AStarRunnerPawn::HandleAction(EStarAction Action, EStarPhase Phase)
{
	switch (Phase)
	{
	case EStarPhase::Begin:
		// Check 3: Begin needs Ready and no active action.
		if (Tracking != EStarTracking::Ready || ActiveAction != EStarAction::None)
		{
			return false;
		}
		// Check 2: gameplay must allow this action now.
		if (!CanStartAction(Action))
		{
			return false;
		}
		BeginAction(Action);
		return true;

	case EStarPhase::Complete:
	case EStarPhase::Cancel:
		// Check 4: must match the active action; Ready is NOT required.
		if (ActiveAction == EStarAction::None || ActiveAction != Action)
		{
			return false;
		}
		if (Phase == EStarPhase::Complete)
		{
			CompleteAction();
		}
		else
		{
			CancelAction();
		}
		return true;

	default:
		return false;
	}
}

void AStarRunnerPawn::BeginAction(EStarAction Action)
{
	ActiveAction = Action;
	// UE leaves Ready itself once it accepts a Begin.
	Tracking = EStarTracking::NotReady;

	switch (Action)
	{
	case EStarAction::JumpLeft:
		StartLaneChange(EStarLane((uint8)Lane - 1));
		break;
	case EStarAction::JumpRight:
		StartLaneChange(EStarLane((uint8)Lane + 1));
		break;
	case EStarAction::JumpingJack:
		bJumping = true;
		JumpElapsed = 0.0f;
		break;
	case EStarAction::Squat:
		SquatTarget = 1.0f;
		break;
	case EStarAction::LeftLeg:
	case EStarAction::RightLeg:
		// Step-over: no locomotion change; the visual/animation hook lives in
		// the offset layer. The cycle still completes on return-to-center.
		break;
	default:
		break;
	}
}

void AStarRunnerPawn::CompleteAction()
{
	// Squat: real stand-up drives the blend back out (documented: the pose is
	// held until actual stand, never auto-released by animation).
	const EStarAction Finished = ActiveAction;
	if (ActiveAction == EStarAction::Squat)
	{
		SquatTarget = 0.0f;
	}
	ActiveAction = EStarAction::None;
	// Count/advance on completed cycles only (never Begin or Cancel).
	OnActionCompleted.Broadcast(Finished);
}

void AStarRunnerPawn::CancelAction()
{
	// Cancel voids the cycle; do not treat it as a completed stand-up.
	if (ActiveAction == EStarAction::Squat)
	{
		SquatTarget = 0.0f;
	}
	if (ActiveAction == EStarAction::JumpingJack)
	{
		bJumping = false;
	}
	ActiveAction = EStarAction::None;
}

void AStarRunnerPawn::HandleTracking(EStarTracking State)
{
	Tracking = State;
	if (State == EStarTracking::Lost && ActiveAction != EStarAction::None)
	{
		// The Go hub already emits a Cancel before Lost; this is a local guard
		// so a stale visual pose never sticks if the Cancel is consumed late.
		CancelAction();
	}
}

// ---------------------------------------------------------------------------
// Movement integration. Everything lands on the current Tick; no buffering.
// ---------------------------------------------------------------------------

void AStarRunnerPawn::UpdateForward(float Dt)
{
	if (!bRunning)
	{
		return;
	}
	FVector Loc = GetActorLocation();
	Loc.X += ForwardSpeed * Dt;
	SetActorLocation(Loc);
}

void AStarRunnerPawn::StartLaneChange(EStarLane Target)
{
	Lane = Target;
	bLaneChanging = true;
	LaneChangeElapsed = 0.0f;
	// Lane change moves the actual pawn (collision + triggers live on the
	// capsule), anchored to the run's center-line Y captured at spawn.
	LaneStartY = GetActorLocation().Y;
	LaneTargetY = CenterLineY + ((int32)Target - 1) * LaneSpacing;
}

void AStarRunnerPawn::UpdateLane(float Dt)
{
	if (!bLaneChanging)
	{
		return;
	}
	LaneChangeElapsed += Dt;
	const float Alpha = FMath::Clamp(LaneChangeElapsed / LaneChangeDuration, 0.0f, 1.0f);
	// Smoothstep eases the lateral move; no jarring mesh snap.
	const float Smooth = Alpha * Alpha * (3.0f - 2.0f * Alpha);
	FVector Loc = GetActorLocation();
	Loc.Y = FMath::Lerp(LaneStartY, LaneTargetY, Smooth);
	SetActorLocation(Loc);
	if (Alpha >= 1.0f)
	{
		bLaneChanging = false;
	}
}

void AStarRunnerPawn::UpdateJump(float Dt)
{
	if (!bJumping)
	{
		return;
	}
	JumpElapsed += Dt;
	const float Alpha = FMath::Clamp(JumpElapsed / JumpDuration, 0.0f, 1.0f);
	// Sine arc: up then land, over JumpDuration.
	CurrentOffsetZ = FMath::Sin(Alpha * PI) * JumpHeight;
	if (Alpha >= 1.0f)
	{
		bJumping = false;
		CurrentOffsetZ = 0.0f;
	}
}

void AStarRunnerPawn::UpdateSquat(float Dt)
{
	if (FMath::IsNearlyEqual(SquatAlpha, SquatTarget))
	{
		SquatAlpha = SquatTarget;
	}
	else
	{
		const float Step = Dt / FMath::Max(SquatBlendTime, KINDA_SMALL_NUMBER);
		SquatAlpha = FMath::Clamp(SquatAlpha + (SquatTarget > SquatAlpha ? Step : -Step), 0.0f, 1.0f);
	}
}

void AStarRunnerPawn::ApplyVisualOffset()
{
	// Jump arc (Z up) and squat (Z down) compose on the visual root, so the
	// capsule keeps a stable footprint for collision while the visible body
	// performs the action. Lane change moves the pawn body directly.
	const float Z = CurrentOffsetZ - SquatAlpha * SquatDrop;
	VisualRoot->SetRelativeLocation(FVector(0.0f, 0.0f, Z));
}
