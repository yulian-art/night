// Copyright 向星而行. Generic task station: post office / lamp / flower stand share one actor.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StarTypes.h"
#include "StarStation.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UPointLightComponent;

// One task point on the route. A station is configured with the action steps
// it requires (e.g. a single JumpingJack to light a lamp). The LevelDirector
// owns progression; the station only tracks its own required steps and lit
// state, so post office / lamp / flower stand differ only by mesh and tuning.
UCLASS()
class STARJOURNEY_API AStarStation : public AActor
{
	GENERATED_BODY()

public:
	AStarStation();

	// The ordered action steps this station requires, e.g. {JumpingJack} or
	// {LeftLeg, RightLeg}. Set by the Director at spawn.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Star|Station")
	TArray<EStarAction> RequiredSteps;

	// World X at which the runner must stop to interact (documented: clamp
	// the stop to the task point; a dropped frame cannot skip it).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Star|Station")
	float StopX = 0.0f;

	// True once every required step has been completed.
	UFUNCTION(BlueprintPure, Category = "Star|Station")
	bool IsComplete() const { return bComplete; }

	// Index of the next required step, for HUD hints.
	UFUNCTION(BlueprintPure, Category = "Star|Station")
	int32 GetNextStepIndex() const { return NextStep; }

	// The action the player must perform now, or None if complete.
	UFUNCTION(BlueprintPure, Category = "Star|Station")
	EStarAction GetRequiredAction() const;

	// The runner reports a completed action cycle while stopped here.
	// Returns true if it advanced the station.
	bool OfferAction(EStarAction Action);

	// Light-up presentation hook (drives the point light and any burst).
	UFUNCTION(BlueprintImplementableEvent, Category = "Star|Station")
	void OnLit();

	// Set the lamp glow directly (used by Director/BP to ramp intensity).
	UFUNCTION(BlueprintCallable, Category = "Star|Station")
	void SetGlow(float Intensity);

protected:
	virtual void BeginPlay() override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<UPointLightComponent> Glow;

	// Warm color for the lit lamp.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Station")
	FLinearColor LitColor = FLinearColor(1.0f, 0.82f, 0.55f, 1.0f);

	// Peak lamp intensity once lit.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Station")
	float LitIntensity = 240.0f;

private:
	int32 NextStep = 0;
	bool bComplete = false;
};
