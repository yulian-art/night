// Copyright 向星而行. Level controller: fixed route, task stops, scoring, seed.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "StarTypes.h"
#include "StarLevelDirector.generated.h"

class AStarRunnerPawn;
class AStarStation;
class UStarSaveQueueComponent;

// Owns the run for one level: the runner advances automatically, clamps to a
// stop at each task station, waits for the required action cycle, lights the
// station, then continues. When all stations are complete and the finish line
// is crossed, it settles the seed (StarSeed) and reports completion.
//
// This is the single authority for progression and scoring, per the design
// doc's "unique task-completion and settlement entry".
UCLASS()
class STARJOURNEY_API AStarLevelDirector : public AActor
{
	GENERATED_BODY()

public:
	AStarLevelDirector();

	virtual void Tick(float DeltaSeconds) override;

	// Wire up the run. Called from Blueprint/level script after spawn.
	UFUNCTION(BlueprintCallable, Category = "Star|Director")
	void InitializeRun(AStarRunnerPawn* InRunner, const TArray<AStarStation*>& InStations);

	// The runner calls this when it completes an action cycle.
	UFUNCTION(BlueprintCallable, Category = "Star|Director")
	void NotifyActionCompleted(EStarAction Action);

	// ---- Run state for HUD -------------------------------------------------

	UFUNCTION(BlueprintPure, Category = "Star|Director")
	int32 GetCompletedCount() const { return CompletedCount; }

	UFUNCTION(BlueprintPure, Category = "Star|Director")
	int32 GetTotalStations() const { return Stations.Num(); }

	UFUNCTION(BlueprintPure, Category = "Star|Director")
	bool IsLevelComplete() const { return bLevelComplete; }

	// Starlight: collected glow units (documented floor(t * 1.7) is an
	// AutoDemo rule; here we count completed stations + jack bonuses).
	UFUNCTION(BlueprintPure, Category = "Star|Director")
	int32 GetStarlight() const { return Starlight; }

	// Fired when the level is settled (all stations + finish). Returns the
	// action counts for SaveRun on the Go side.
	UFUNCTION(BlueprintPure, Category = "Star|Director")
	int32 GetActionCount(EStarAction Action) const;

	// Blueprint hook: level settled; play the finale.
	UFUNCTION(BlueprintImplementableEvent, Category = "Star|Director")
	void OnLevelSettled(int32 FinalStarlight);

	// Blueprint hook: a station lit; play its 1.4s ceremony.
	UFUNCTION(BlueprintImplementableEvent, Category = "Star|Director")
	void OnStationLit(int32 StationIndex, int32 CompletedCount);

protected:
	virtual void BeginPlay() override;

	// Stable level id (1 风邮原野 / 2 回声森林 / 3 云鲸星海), sent as Run.level_id.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Director")
	int32 LevelId = 2;

	// Finish-line world X; crossing it (with all stations done) settles.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Director")
	float FinishX = 10400.0f;

	// How early before StopX the runner begins easing to the stop.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Star|Director")
	float StopApproachDistance = 240.0f;

	// Durable outbox for settled runs. Owned here because settling is the only
	// place a real run is produced (AutoDemo must never enqueue).
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Star|Components")
	TObjectPtr<UStarSaveQueueComponent> SaveQueue;

private:
	void UpdateStops();
	void Settle();

	// Build the completed-run record and hand it to the outbox, then try to
	// send. Runs exactly once per settled level.
	void SaveSettledRun();

	UPROPERTY()
	TObjectPtr<AStarRunnerPawn> Runner;

	UPROPERTY()
	TArray<TObjectPtr<AStarStation>> Stations;

	// Next station index the runner must stop at.
	int32 NextStation = 0;
	bool bWaitingAtStation = false;
	int32 CompletedCount = 0;
	int32 Starlight = 0;
	bool bLevelComplete = false;

	// Run start time on the game clock, for Run.active_ms.
	double RunStartedAtSeconds = 0.0;

	// Completed action-cycle counts, keyed by action (for SaveRun).
	TMap<EStarAction, int32> ActionCounts;
};
