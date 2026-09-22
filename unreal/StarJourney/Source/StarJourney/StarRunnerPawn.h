// Copyright 向星而行. Three-lane runner driven by action events.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "StarAnimTypes.h"
#include "StarTypes.h"
#include "StarRunnerPawn.generated.h"

class UCameraComponent;
class UCapsuleComponent;
class USceneComponent;
class USkeletalMeshComponent;
class UAnimInstance;
class UAnimMontage;
class UStarInputComponent;

// Broadcast when an action cycle completes (never on Begin/Cancel). The
// LevelDirector listens to advance task stations and count cycles.
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FStarOnActionCompleted, EStarAction, Action);

// The player character: an automatically-forward-moving runner on three
// lanes. It does not read keyboard/gRPC directly; it consumes EStarAction
// cycles through UStarInputComponent, which unifies keyboard and the
// WebSocket gesture feed behind one interface.
//
// Real-time rule (anti-latency): every action mutates movement state in the
// same Tick it is received. There is no queue, no polling timer, no
// Sequencer. Begin lands on the frame it arrives.
UCLASS()
class STARJOURNEY_API AStarRunnerPawn : public APawn
{
	GENERATED_BODY()

public:
	AStarRunnerPawn();

	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	// ---- External control (LevelDirector) ---------------------------------

	// Pause/resume forward motion at a station or on tracking loss.
	UFUNCTION(BlueprintCallable, Category = "Star|Runner")
	void SetRunning(bool bNewRunning);

	UFUNCTION(BlueprintPure, Category = "Star|Runner")
	bool IsRunning() const { return bRunning; }

	// ---- Action entry point (called by the input component) ----------------

	// Feed one action cycle. Returns true if the action was accepted this
	// frame. UE applies the four documented input checks before acting.
	UFUNCTION(BlueprintCallable, Category = "Star|Runner")
	bool HandleAction(EStarAction Action, EStarPhase Phase);

	// Feed a tracking-state change (Lost/NotReady/Ready).
	UFUNCTION(BlueprintCallable, Category = "Star|Runner")
	void HandleTracking(EStarTracking State);

	// ---- State for HUD / Director ------------------------------------------

	UFUNCTION(BlueprintPure, Category = "Star|Runner")
	EStarLane GetLane() const { return Lane; }

	UFUNCTION(BlueprintPure, Category = "Star|Runner")
	bool IsActionActive() const { return ActiveAction != EStarAction::None; }

	UFUNCTION(BlueprintPure, Category = "Star|Runner")
	EStarAction GetActiveAction() const { return ActiveAction; }

	UFUNCTION(BlueprintPure, Category = "Star|Runner")
	EStarTracking GetTracking() const { return Tracking; }

	UFUNCTION(BlueprintPure, Category = "Star|Runner")
	bool IsReady() const { return Tracking == EStarTracking::Ready; }

	// LevelDirector subscribes here to count completed cycles and advance stops.
	UPROPERTY(BlueprintAssignable, Category = "Star|Runner")
	FStarOnActionCompleted OnActionCompleted;

	// The framing camera, for systems that need to place prompts/effects in
	// view space instead of re-deriving the framing themselves.
	UFUNCTION(BlueprintPure, Category = "Star|Runner")
	UCameraComponent* GetRunnerCamera() const { return Camera; }

	// ---- Animation contract (read by the character AnimBP) ------------------

	// Which pose the body should hold right now. The AnimBP reads this instead
	// of re-deriving gameplay state, so the graph and the gameplay code can
	// never disagree about what the runner is doing.
	UFUNCTION(BlueprintPure, Category = "Star|Anim")
	EStarAnimState GetAnimState() const;

	// Squat blend: 0 = standing, 1 = fully crouched. Exposed because the squat
	// pose is owned by the AnimBP (there is deliberately no squat montage), so
	// the graph needs this both to blend in and to blend back out when the
	// player really stands up.
	UFUNCTION(BlueprintPure, Category = "Star|Anim")
	float GetSquatAlpha() const { return SquatAlpha; }

protected:
	virtual void BeginPlay() override;

	// ---- Movement tuning (editable per-instance / in Blueprint) -------------

	// Constant forward speed in cm/s while running.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Movement")
	float ForwardSpeed = 700.0f;

	// Lane lateral spacing in cm (three lanes at Y = -LaneSpacing, 0, +LaneSpacing).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Movement")
	float LaneSpacing = 180.0f;

	// Lane-change duration in seconds (documented 0.3-0.45s window).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Movement")
	float LaneChangeDuration = 0.38f;

	// Jump arc height in cm for a jumping jack.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Movement")
	float JumpHeight = 90.0f;

	// Jump (rising+landing) duration in seconds.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Movement")
	float JumpDuration = 0.7f;

	// How far the capsule/body drops while squatting, in cm.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Movement")
	float SquatDrop = 32.0f;

	// Blend time in/out of the squat pose.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Movement")
	float SquatBlendTime = 0.15f;

	// ---- Fixed rear-view camera tuning --------------------------------------
	// The doc pins the camera to forward motion and to the road's center line,
	// so none of these follow the runner's lane: lateral framing stays still
	// while the body swaps lanes, keeping the action prompts readable.

	// How far behind the runner (along world -X) the camera sits, in cm.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Camera")
	float CameraBackOffset = 1350.0f;

	// Fixed world Z for the camera, in cm. Independent of the jump/squat
	// offsets on the visual body, which must never bounce the frame.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Camera")
	float CameraHeight = 440.0f;

	// Fixed pitch in degrees, applied as world rotation; yaw stays 0 so the
	// road always vanishes at the same point on screen.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Camera")
	float CameraPitch = -6.0f;

	// Fixed horizontal FOV in degrees (the cinematic authored 55 for this
	// framing). Applied to the component at construction and re-applied in
	// BeginPlay, so a per-instance override here actually takes effect.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Camera")
	float CameraFov = 55.0f;

	// ---- Animation assets (assigned in the editor, never hard-coded) --------
	// C++ holds no asset paths on purpose: the skeleton, the blueprint and the
	// montages live in the project's content and must stay swappable without a
	// code change or a recompile.

	// Animation blueprint for the skeletal mesh. Left unset, the placeholder
	// body on VisualRoot is simply what the player sees, and nothing breaks.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Star|Anim")
	TSubclassOf<UAnimInstance> AnimClass;

	// One-shot montage per action. A null entry is skipped silently so the game
	// stays playable while the art is still being produced.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Star|Anim")
	TObjectPtr<UAnimMontage> JackMontage;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Star|Anim")
	TObjectPtr<UAnimMontage> LaneLeftMontage;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Star|Anim")
	TObjectPtr<UAnimMontage> LaneRightMontage;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Star|Anim")
	TObjectPtr<UAnimMontage> LegLeftMontage;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Star|Anim")
	TObjectPtr<UAnimMontage> LegRightMontage;

	// ---- Components ----------------------------------------------------------

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<UCapsuleComponent> Capsule;

	// Visual root; the assembled astronaut meshes attach under this so motion
	// offsets (lane/jump/squat) never fight the capsule's world location.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<USceneComponent> VisualRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<UStarInputComponent> Input;

	// Fixed rear-view framing camera (doc: 55 degree FOV, the small traveller
	// low in frame with the road running to the vanishing point).
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<UCameraComponent> Camera;

	// Full-body skeletal mesh (SK_Hero / SK_Fox). Presentation only: the capsule
	// stays the collision authority, so no animation can push the runner off the
	// route or through a station trigger, and no root motion can desync the
	// director's clamped stopping logic.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<USkeletalMeshComponent> Mesh;

private:
	// Per-frame movement integration.
	void UpdateForward(float Dt);
	void UpdateLane(float Dt);
	void UpdateJump(float Dt);
	void UpdateSquat(float Dt);
	void ApplyVisualOffset();

	// Re-pin the camera to world space after movement has been integrated.
	void UpdateCamera();

	bool CanStartAction(EStarAction Action) const;
	void BeginAction(EStarAction Action);
	void CompleteAction();
	void CancelAction();

	void StartLaneChange(EStarLane Target);

	// ---- Montage plumbing ---------------------------------------------------

	// Montage that represents one action, or null when the action has none
	// (squat) or the asset has not been assigned yet.
	UAnimMontage* MontageForAction(EStarAction Action) const;

	// Start the montage for a new cycle, and finish the one a cycle is leaving.
	// Both are no-ops when there is no mesh, no anim instance or no montage.
	void PlayActionMontage(EStarAction Action);
	void StopActionMontage(EStarAction Action);

	bool bRunning = true;
	EStarTracking Tracking = EStarTracking::NotReady;

	// Center-line Y captured at spawn; lanes sit at CenterLineY + (lane-1)*spacing.
	float CenterLineY = 0.0f;

	EStarLane Lane = EStarLane::Center;
	// Lane-change interpolation state (moves the pawn body, not just the visual).
	float LaneStartY = 0.0f;
	float LaneTargetY = 0.0f;
	float LaneChangeElapsed = 0.0f;
	bool bLaneChanging = false;

	// Active action cycle.
	EStarAction ActiveAction = EStarAction::None;

	// Jump-arc state (jumping jack).
	float JumpElapsed = 0.0f;
	bool bJumping = false;

	// Squat blend state (0 = standing, 1 = fully squatted).
	float SquatAlpha = 0.0f;
	float SquatTarget = 0.0f;

	// Vertical visual offset from the jump arc, applied to VisualRoot.
	float CurrentOffsetZ = 0.0f;
};
