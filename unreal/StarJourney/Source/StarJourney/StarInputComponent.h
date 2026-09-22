// Copyright 向星而行. Unified action input: keyboard now, WebSocket gestures next.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "StarTypes.h"
#include "StarInputComponent.generated.h"

class AStarRunnerPawn;
class IWebSocket;

// One producer of action cycles for the runner. Keyboard emits Begin on
// key-down and Complete on key-up in the same frame (zero added latency); the
// WebSocket source replays the Go gateway's InputEvent stream identically.
// Both funnel into the owner's HandleAction/HandleTracking, which own the
// four documented gameplay checks.
//
// Local state mirrors the documented UE-side trio: Generation, TrackingState,
// ActiveAction. The component owns the local Generation counter and bumps it
// whenever a new input cycle starts.
UCLASS(ClassGroup = (Star), meta = (BlueprintSpawnableComponent))
class STARJOURNEY_API UStarInputComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UStarInputComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	// Bind default keyboard controls (call from SetupPlayerInputComponent).
	// A/D = jump left/right, S = squat, Space = jumping jack, Q/E = legs.
	void BindKeyboard(UInputComponent* PlayerInputComponent);

	// ---- WebSocket gesture feed (Go gateway) -------------------------------

	// Connect to the Go gateway and start a new generation. Call after keyboard
	// is validated; safe to leave disconnected for keyboard-only testing.
	UFUNCTION(BlueprintCallable, Category = "Star|Input")
	void ConnectGestures(const FString& WebSocketUrl);

	UFUNCTION(BlueprintCallable, Category = "Star|Input")
	void DisconnectGestures();

	// Current local generation (string form used on the wire).
	UFUNCTION(BlueprintPure, Category = "Star|Input")
	uint64 GetGeneration() const { return Generation; }

protected:
	// Owner helpers.
	AStarRunnerPawn* Runner() const;

	// Bump to a fresh generation (Unix-nanos, matching star-smoke's scheme).
	uint64 NextGeneration();

	// Keyboard handlers (UFUNCTION required for BindKey member-pointer overload).
	UFUNCTION() void OnJumpLeftPressed();
	UFUNCTION() void OnJumpRightPressed();
	UFUNCTION() void OnSquatPressed();
	UFUNCTION() void OnSquatReleased();
	UFUNCTION() void OnJackPressed();
	UFUNCTION() void OnLeftLegPressed();
	UFUNCTION() void OnLeftLegReleased();
	UFUNCTION() void OnRightLegPressed();
	UFUNCTION() void OnRightLegReleased();

	void PressAction(EStarAction Action);
	void ReleaseAction(EStarAction Action);

	// WebSocket event handling (UFUNCTION required for IWebSocket delegates).
	UFUNCTION() void OnWSConnected();
	UFUNCTION() void OnWSError(const FString& Error);
	UFUNCTION() void OnWSMessage(const FString& Message);
	UFUNCTION() void OnWSClosed(int32 StatusCode, const FString& Reason, bool bWasClean);
	void HandleStreamEvent(const FStarInputEvent& Event);

private:
	UPROPERTY()
	TObjectPtr<AStarRunnerPawn> CachedRunner;

	// Local input state (documented UE-side trio).
	uint64 Generation = 0;
	EStarTracking Tracking = EStarTracking::Ready; // keyboard starts ready
	EStarAction ActiveAction = EStarAction::None;

	bool bGesturesConnected = false;
	FString GestureUrl;
	TSharedPtr<IWebSocket> Socket;
};
